package worker

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/algorithm"
	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
)

// Processor implements the JobProcessor interface
type Processor struct {
	redisClient   *redis.Client
	haIntegration *homeassistant.Integration
}

// NewProcessor creates a new job processor
func NewProcessor(redisClient *redis.Client, haIntegration *homeassistant.Integration) *Processor {
	return &Processor{
		redisClient:   redisClient,
		haIntegration: haIntegration,
	}
}

// setLastActuated sets the LastActuated timestamp for a zone to the current time
func setLastActuated(zone *models.ZoneState) {
	now := time.Now()
	zone.LastActuated = &now
}

// ProcessCalculateTemp calculates the main thermostat target temperature
func (p *Processor) ProcessCalculateTemp(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error) {
	logger.Info("Processing temperature calculation job")

	// Load zones from Redis
	zones, err := p.loadZones(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load zones: %w", err)
	}

	// Load global config
	config, err := p.loadConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	// Get current main target temperature
	mainClimate, err := p.loadMainClimate(ctx)
	if err != nil {
		logger.Warn("Failed to load main climate state: %v", err)
		mainClimate = &models.MainClimateState{TargetTemperature: 20.0}
	}

	// Calculate new target temperature
	newTarget, shouldUpdate := algorithm.CalculateMainTargetTemperature(zones, *config, mainClimate.TargetTemperature)

	result := map[string]interface{}{
		"should_update":  shouldUpdate,
		"current_target": mainClimate.TargetTemperature,
	}

	if shouldUpdate {
		result["new_target"] = newTarget
		logger.Info("Calculated new target temperature: %.1f°C (was %.1f°C)", newTarget, mainClimate.TargetTemperature)

		// Update via Home Assistant if integration is available
		if p.haIntegration != nil && p.haIntegration.IsEnabled() && config.MainClimateEntityID != "" {
			if err := p.haIntegration.SetMainTemperature(ctx, config.MainClimateEntityID, newTarget); err != nil {
				logger.Warn("Failed to update main temperature via HA: %v", err)
			} else {
				logger.Debug("Updated main temperature via Home Assistant: %.1f°C", newTarget)
			}
		}
	} else {
		logger.Debug("No temperature update needed (current: %.1f°C)", mainClimate.TargetTemperature)
	}

	return result, nil
}

// ProcessUpdateValves updates valve states using enhanced valve management
func (p *Processor) ProcessUpdateValves(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error) {
	logger.Info("Processing valve update job")

	// Load zones from Redis
	zones, err := p.loadZones(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load zones: %w", err)
	}

	// Load global config
	config, err := p.loadConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	// Update satisfaction status for all zones
	for i := range zones {
		zones[i].Satisfaction = algorithm.DetermineZoneSatisfaction(zones[i], config.SatisfactionEpsilon)
	}

	// Plan valve operations with enhanced management
	openOps, closeOps := algorithm.PlanValveOperations(zones, config.ValveActuationDelay)

	logger.Info("Planned valve operations: %d to open, %d to close", len(openOps), len(closeOps))

	// Execute operations with open-first-then-close sequencing
	executedOps := algorithm.ExecuteValveOperations(openOps, closeOps, zones, config.MinValvesOpen)

	logger.Info("Executed %d valve operations", len(executedOps))

	// Apply operations to Home Assistant if integration is available
	appliedCount := 0
	if p.haIntegration != nil && p.haIntegration.IsEnabled() {
		// Build a map for efficient zone lookup by ID
		zoneByID := make(map[string]*models.ZoneState, len(zones))
		for i := range zones {
			zoneByID[zones[i].ID] = &zones[i]
		}

		for _, op := range executedOps {
			zone, ok := zoneByID[op.ZoneID]
			if !ok || zone == nil || zone.ValveSwitchEntity == "" {
				logger.Warn("Cannot execute operation for zone %s: zone or valve entity not found", op.ZoneID)
				continue
			}

			// Apply the operation
			shouldOpen := op.Operation == "open"
			if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, shouldOpen); err != nil {
				logger.Warn("Failed to set valve state for zone %s: %v", zone.ID, err)
			} else {
				appliedCount++
				logger.Debug("Set valve %s to %s for zone %s (priority: %d)",
					zone.ValveSwitchEntity, op.Operation, zone.ID, zone.Priority)

				// Save updated zone state to Redis
				if err := p.saveZone(ctx, zone); err != nil {
					logger.Warn("Failed to save zone state: %v", err)
				}
			}
		}
	}

	// Check and enforce minimum valves using priority-based selection
	minValvesToOpen := algorithm.CheckMinimumValvesByPriority(zones, config.MinValvesOpen)
	if len(minValvesToOpen) > 0 {
		logger.Info("Opening %d fallback valves to meet minimum requirement", len(minValvesToOpen))

		if p.haIntegration != nil && p.haIntegration.IsEnabled() {
			// Build a map for efficient zone lookup by ID
			zoneByID := make(map[string]*models.ZoneState, len(zones))
			for i := range zones {
				zoneByID[zones[i].ID] = &zones[i]
			}

			for _, zoneID := range minValvesToOpen {
				zone, ok := zoneByID[zoneID]
				if !ok || zone == nil || zone.ValveSwitchEntity == "" {
					continue
				}

				if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, true); err != nil {
					logger.Warn("Failed to open fallback valve for zone %s: %v", zone.ID, err)
				} else {
					appliedCount++
					logger.Debug("Opened fallback valve for zone %s (priority: %d)", zone.ID, zone.Priority)

					// Update zone state and set LastActuated timestamp
					zone.ValveState = "open"
					setLastActuated(zone)
					
					if err := p.saveZone(ctx, zone); err != nil {
						logger.Warn("Failed to save zone state: %v", err)
					}
				}
			}
		}
	}

	return map[string]interface{}{
		"planned_open":     len(openOps),
		"planned_close":    len(closeOps),
		"executed":         len(executedOps),
		"applied":          appliedCount,
		"fallback_opened":  len(minValvesToOpen),
	}, nil
}

// ProcessSafetyCheck performs safety checks on the system
func (p *Processor) ProcessSafetyCheck(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error) {
	logger.Info("Processing safety check job")

	// Load zones from Redis
	zones, err := p.loadZones(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load zones: %w", err)
	}

	// Load global config
	config, err := p.loadConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	// Count open valves
	openCount := 0
	enabledCount := 0
	for _, z := range zones {
		if z.Enabled {
			enabledCount++
			if z.ValveState == "open" {
				openCount++
			}
		}
	}

	result := map[string]interface{}{
		"enabled_zones": enabledCount,
		"open_valves":   openCount,
		"min_required":  config.MinValvesOpen,
		"status":        "ok",
	}

	// Check if minimum valves are open
	if openCount < config.MinValvesOpen {
		logger.Warn("SAFETY WARNING: Only %d valves open, minimum required is %d", openCount, config.MinValvesOpen)
		result["status"] = "warning"
		result["message"] = fmt.Sprintf("Insufficient open valves: %d < %d", openCount, config.MinValvesOpen)

		// Attempt to open fallback valves
		minValvesToOpen := algorithm.CheckMinimumValvesByPriority(zones, config.MinValvesOpen)
		if len(minValvesToOpen) > 0 && p.haIntegration != nil && p.haIntegration.IsEnabled() {
			logger.Info("Attempting to open %d fallback valves", len(minValvesToOpen))
			openedCount := 0

			// Build a map for efficient zone lookup by ID
			zoneByID := make(map[string]*models.ZoneState, len(zones))
			for i := range zones {
				zoneByID[zones[i].ID] = &zones[i]
			}

			for _, zoneID := range minValvesToOpen {
				zone, ok := zoneByID[zoneID]
				if !ok || zone == nil || zone.ValveSwitchEntity == "" {
					continue
				}

				if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, true); err != nil {
					logger.Error("Failed to open safety fallback valve for zone %s: %v", zone.ID, err)
				} else {
					openedCount++
					zone.ValveState = "open"
					setLastActuated(zone)
					
					if err := p.saveZone(ctx, zone); err != nil {
						logger.Error("Failed to persist safety fallback valve state for zone %s: %v", zone.ID, err)
					}
				}
			}

			result["fallback_opened"] = openedCount
		}
	}

	return result, nil
}

// loadZones loads all zones from Redis
func (p *Processor) loadZones(ctx context.Context) ([]models.ZoneState, error) {
	zoneKeys, err := p.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return nil, err
	}

	zones := []models.ZoneState{}
	for _, key := range zoneKeys {
		zone, err := p.loadZoneByKey(ctx, key)
		if err != nil {
			logger.Warn("Failed to load zone %s: %v", key, err)
			continue
		}
		zones = append(zones, *zone)
	}

	return zones, nil
}

// loadZoneByKey loads a zone from Redis by its key
func (p *Processor) loadZoneByKey(ctx context.Context, key string) (*models.ZoneState, error) {
	data, err := p.redisClient.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}

	zone := &models.ZoneState{
		ID:                      data["id"],
		Name:                    data["name"],
		TemperatureSensorEntity: data["temperature_sensor_entity_id"],
		ValveSwitchEntity:       data["valve_switch_entity_id"],
		ValveState:              data["valve_state"],
	}

	// Parse numeric fields
	if val, ok := data["current_temperature"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse current_temperature for zone %s: %v", zone.ID, err)
		} else {
			zone.CurrentTemperature = f
		}
	}
	if val, ok := data["target_temperature"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse target_temperature for zone %s: %v", zone.ID, err)
		} else {
			zone.TargetTemperature = f
		}
	}
	if val, ok := data["opening_offset"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse opening_offset for zone %s: %v", zone.ID, err)
		} else {
			zone.OpeningOffset = f
		}
	}
	if val, ok := data["closing_offset"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse closing_offset for zone %s: %v", zone.ID, err)
		} else {
			zone.ClosingOffset = f
		}
	}
	if val, ok := data["priority"]; ok && val != "" {
		if p, err := strconv.Atoi(val); err != nil {
			logger.Warn("Failed to parse priority for zone %s: %v", zone.ID, err)
		} else {
			zone.Priority = p
		}
	}

	// Parse boolean fields
	if val, ok := data["enabled"]; ok {
		zone.Enabled = val == "true" || val == "1"
	}
	if val, ok := data["is_fallback_valve"]; ok {
		zone.IsFallbackValve = val == "true" || val == "1"
	}

	// Parse timestamp fields
	if val, ok := data["last_actuated"]; ok && val != "" {
		if timestamp, err := strconv.ParseInt(val, 10, 64); err == nil {
			t := time.Unix(timestamp, 0)
			zone.LastActuated = &t
		} else {
			logger.Warn("Failed to parse last_actuated for zone %s: %v", zone.ID, err)
		}
	}
	if val, ok := data["valve_lock_expiration"]; ok && val != "" {
		if timestamp, err := strconv.ParseInt(val, 10, 64); err == nil {
			t := time.Unix(timestamp, 0)
			zone.ValveLockExpiration = &t
		} else {
			logger.Warn("Failed to parse valve_lock_expiration for zone %s: %v", zone.ID, err)
		}
	}

	return zone, nil
}

// saveZone saves a zone to Redis
func (p *Processor) saveZone(ctx context.Context, zone *models.ZoneState) error {
	key := fmt.Sprintf("multizone:zone:%s", zone.ID)

	updates := map[string]interface{}{
		"valve_state": zone.ValveState,
	}

	if zone.LastActuated != nil {
		updates["last_actuated"] = zone.LastActuated.Unix()
	}

	if zone.ValveLockExpiration != nil {
		updates["valve_lock_expiration"] = zone.ValveLockExpiration.Unix()
	}

	return p.redisClient.HSet(ctx, key, updates)
}

// loadConfig loads the global configuration from Redis
func (p *Processor) loadConfig(ctx context.Context) (*models.GlobalConfig, error) {
	data, err := p.redisClient.HGetAll(ctx, "multizone:config")
	if err != nil {
		return nil, err
	}

	config := &models.GlobalConfig{
		MainClimateEntityID: data["main_climate_entity_id"],
	}

	// Parse numeric fields with defaults
	if val, ok := data["main_target_all_zones_satisfied"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse main_target_all_zones_satisfied: %v", err)
		} else {
			config.MainTargetAllZonesSatisfied = f
		}
	}
	if val, ok := data["slider_position"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse slider_position: %v", err)
		} else {
			config.SliderPosition = f
		}
	}
	if val, ok := data["min_valves_open"]; ok && val != "" {
		if i, err := strconv.Atoi(val); err != nil {
			logger.Warn("Failed to parse min_valves_open: %v", err)
		} else {
			config.MinValvesOpen = i
		}
	}
	if val, ok := data["main_min_temp"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse main_min_temp: %v", err)
		} else {
			config.MainMinTemp = f
		}
	}
	if val, ok := data["main_max_temp"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse main_max_temp: %v", err)
		} else {
			config.MainMaxTemp = f
		}
	}
	if val, ok := data["main_change_threshold"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse main_change_threshold: %v", err)
		} else {
			config.MainChangeThreshold = f
		}
	}
	if val, ok := data["valve_actuation_delay"]; ok && val != "" {
		if i, err := strconv.Atoi(val); err != nil {
			logger.Warn("Failed to parse valve_actuation_delay: %v", err)
		} else {
			config.ValveActuationDelay = i
		}
	}
	if val, ok := data["coordinator_interval"]; ok && val != "" {
		if i, err := strconv.Atoi(val); err != nil {
			logger.Warn("Failed to parse coordinator_interval: %v", err)
		} else {
			config.CoordinatorInterval = i
		}
	}
	if val, ok := data["satisfaction_eps"]; ok && val != "" {
		if f, err := strconv.ParseFloat(val, 64); err != nil {
			logger.Warn("Failed to parse satisfaction_eps: %v", err)
		} else {
			config.SatisfactionEpsilon = f
		}
	}

	// Parse boolean fields
	if val, ok := data["use_average_mode"]; ok {
		config.UseAverageMode = val == "true" || val == "1"
	}

	return config, nil
}

// loadMainClimate loads the main climate state from Redis
func (p *Processor) loadMainClimate(ctx context.Context) (*models.MainClimateState, error) {
	data, err := p.redisClient.HGetAll(ctx, "multizone:main_climate")
	if err != nil {
		return nil, err
	}

	climate := &models.MainClimateState{
		EntityID: data["entity_id"],
		HVACMode: data["hvac_mode"],
		HVACAction: data["hvac_action"],
	}

	if val, ok := data["current_temperature"]; ok {
		climate.CurrentTemperature, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["target_temperature"]; ok {
		climate.TargetTemperature, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["outdoor_temperature"]; ok {
		climate.OutdoorTemperature, _ = strconv.ParseFloat(val, 64)
	}

	return climate, nil
}
