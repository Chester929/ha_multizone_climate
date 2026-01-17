package worker

import (
	"context"
	"fmt"
	"log"
	"strconv"

	"github.com/chester929/ha_multizone_climate/logic/internal/algorithm"
	"github.com/chester929/ha_multizone_climate/logic/internal/homeassistant"
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

// ProcessCalculateTemp calculates the main thermostat target temperature
func (p *Processor) ProcessCalculateTemp(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log.Println("Processing temperature calculation job")

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
		log.Printf("Warning: Failed to load main climate state: %v", err)
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
		log.Printf("Calculated new target temperature: %.1f°C (was %.1f°C)", newTarget, mainClimate.TargetTemperature)

		// Update via Home Assistant if integration is available
		if p.haIntegration != nil && p.haIntegration.IsEnabled() && config.MainClimateEntityID != "" {
			if err := p.haIntegration.SetMainTemperature(ctx, config.MainClimateEntityID, newTarget); err != nil {
				log.Printf("Warning: Failed to update main temperature via HA: %v", err)
			} else {
				log.Printf("Updated main temperature via Home Assistant: %.1f°C", newTarget)
			}
		}
	} else {
		log.Printf("No temperature update needed (current: %.1f°C)", mainClimate.TargetTemperature)
	}

	return result, nil
}

// ProcessUpdateValves updates valve states using enhanced valve management
func (p *Processor) ProcessUpdateValves(ctx context.Context, params map[string]interface{}) (map[string]interface{}, error) {
	log.Println("Processing valve update job")

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

	log.Printf("Planned valve operations: %d to open, %d to close", len(openOps), len(closeOps))

	// Execute operations with open-first-then-close sequencing
	executedOps := algorithm.ExecuteValveOperations(openOps, closeOps, zones, config.MinValvesOpen)

	log.Printf("Executed %d valve operations", len(executedOps))

	// Apply operations to Home Assistant if integration is available
	appliedCount := 0
	if p.haIntegration != nil && p.haIntegration.IsEnabled() {
		for _, op := range executedOps {
			// Find the zone
			var zone *models.ZoneState
			for i := range zones {
				if zones[i].ID == op.ZoneID {
					zone = &zones[i]
					break
				}
			}

			if zone == nil || zone.ValveSwitchEntity == "" {
				log.Printf("Warning: Cannot execute operation for zone %s: zone or valve entity not found", op.ZoneID)
				continue
			}

			// Apply the operation
			shouldOpen := op.Operation == "open"
			if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, shouldOpen); err != nil {
				log.Printf("Warning: Failed to set valve state for zone %s: %v", zone.ID, err)
			} else {
				appliedCount++
				log.Printf("Set valve %s to %s for zone %s (priority: %d)",
					zone.ValveSwitchEntity, op.Operation, zone.ID, zone.Priority)

				// Save updated zone state to Redis
				if err := p.saveZone(ctx, zone); err != nil {
					log.Printf("Warning: Failed to save zone state: %v", err)
				}
			}
		}
	}

	// Check and enforce minimum valves using priority-based selection
	minValvesToOpen := algorithm.CheckMinimumValvesByPriority(zones, config.MinValvesOpen)
	if len(minValvesToOpen) > 0 {
		log.Printf("Opening %d fallback valves to meet minimum requirement", len(minValvesToOpen))

		if p.haIntegration != nil && p.haIntegration.IsEnabled() {
			for _, zoneID := range minValvesToOpen {
				// Find the zone
				var zone *models.ZoneState
				for i := range zones {
					if zones[i].ID == zoneID {
						zone = &zones[i]
						break
					}
				}

				if zone == nil || zone.ValveSwitchEntity == "" {
					continue
				}

				if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, true); err != nil {
					log.Printf("Warning: Failed to open fallback valve for zone %s: %v", zone.ID, err)
				} else {
					appliedCount++
					log.Printf("Opened fallback valve for zone %s (priority: %d)", zone.ID, zone.Priority)

					// Save updated zone state
					zone.ValveState = "open"
					if err := p.saveZone(ctx, zone); err != nil {
						log.Printf("Warning: Failed to save zone state: %v", err)
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
	log.Println("Processing safety check job")

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
		log.Printf("SAFETY WARNING: Only %d valves open, minimum required is %d", openCount, config.MinValvesOpen)
		result["status"] = "warning"
		result["message"] = fmt.Sprintf("Insufficient open valves: %d < %d", openCount, config.MinValvesOpen)

		// Attempt to open fallback valves
		minValvesToOpen := algorithm.CheckMinimumValvesByPriority(zones, config.MinValvesOpen)
		if len(minValvesToOpen) > 0 && p.haIntegration != nil && p.haIntegration.IsEnabled() {
			log.Printf("Attempting to open %d fallback valves", len(minValvesToOpen))
			openedCount := 0

			for _, zoneID := range minValvesToOpen {
				var zone *models.ZoneState
				for i := range zones {
					if zones[i].ID == zoneID {
						zone = &zones[i]
						break
					}
				}

				if zone == nil || zone.ValveSwitchEntity == "" {
					continue
				}

				if err := p.haIntegration.SetValveState(ctx, zone.ValveSwitchEntity, true); err != nil {
					log.Printf("Failed to open safety fallback valve for zone %s: %v", zone.ID, err)
				} else {
					openedCount++
					zone.ValveState = "open"
					p.saveZone(ctx, zone)
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
			log.Printf("Warning: Failed to load zone %s: %v", key, err)
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
	if val, ok := data["current_temperature"]; ok {
		zone.CurrentTemperature, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["target_temperature"]; ok {
		zone.TargetTemperature, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["opening_offset"]; ok {
		zone.OpeningOffset, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["closing_offset"]; ok {
		zone.ClosingOffset, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["priority"]; ok {
		p, _ := strconv.Atoi(val)
		zone.Priority = p
	}

	// Parse boolean fields
	if val, ok := data["enabled"]; ok {
		zone.Enabled = val == "true" || val == "1"
	}
	if val, ok := data["is_fallback_valve"]; ok {
		zone.IsFallbackValve = val == "true" || val == "1"
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
	if val, ok := data["main_target_all_zones_satisfied"]; ok {
		config.MainTargetAllZonesSatisfied, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["slider_position"]; ok {
		config.SliderPosition, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["min_valves_open"]; ok {
		config.MinValvesOpen, _ = strconv.Atoi(val)
	}
	if val, ok := data["main_min_temp"]; ok {
		config.MainMinTemp, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["main_max_temp"]; ok {
		config.MainMaxTemp, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["main_change_threshold"]; ok {
		config.MainChangeThreshold, _ = strconv.ParseFloat(val, 64)
	}
	if val, ok := data["valve_actuation_delay"]; ok {
		config.ValveActuationDelay, _ = strconv.Atoi(val)
	}
	if val, ok := data["coordinator_interval"]; ok {
		config.CoordinatorInterval, _ = strconv.Atoi(val)
	}
	if val, ok := data["satisfaction_eps"]; ok {
		config.SatisfactionEpsilon, _ = strconv.ParseFloat(val, 64)
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
