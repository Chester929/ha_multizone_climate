package statistics

import (
	"context"
	"strings"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/models"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
)

// Tracker manages statistics collection and storage
type Tracker struct {
	redisClient *redis.Client
	storage     *Storage
	metrics     *MetricsCalculator
}

// NewTracker creates a new statistics tracker
func NewTracker(redisClient *redis.Client) *Tracker {
	storage := NewStorage(redisClient)
	metrics := NewMetricsCalculator(storage)
	
	return &Tracker{
		redisClient: redisClient,
		storage:     storage,
		metrics:     metrics,
	}
}

// RecordTemperature records a temperature reading for a zone
func (t *Tracker) RecordTemperature(ctx context.Context, zoneID string, temperature float64, timestamp time.Time) error {
	return t.storage.StoreTemperatureReading(ctx, zoneID, temperature, timestamp)
}

// RecordValveActivity records a valve state change
func (t *Tracker) RecordValveActivity(ctx context.Context, zoneID string, state string, timestamp time.Time) error {
	return t.storage.StoreValveActivity(ctx, zoneID, state, timestamp)
}

// RecordZoneSatisfaction records zone satisfaction state
func (t *Tracker) RecordZoneSatisfaction(ctx context.Context, zoneID string, satisfaction string, timestamp time.Time) error {
	return t.storage.StoreZoneSatisfaction(ctx, zoneID, satisfaction, timestamp)
}

// RecordAlgorithmExecution records algorithm execution time
func (t *Tracker) RecordAlgorithmExecution(ctx context.Context, algorithmType string, durationMs int64, timestamp time.Time) error {
	return t.storage.StoreAlgorithmExecution(ctx, algorithmType, durationMs, timestamp)
}

// GetTemperatureHistory retrieves temperature history for a zone
func (t *Tracker) GetTemperatureHistory(ctx context.Context, zoneID string, hours int) ([]TemperatureReading, error) {
	return t.storage.GetTemperatureHistory(ctx, zoneID, hours)
}

// GetValveActivityHistory retrieves valve activity history for a zone
func (t *Tracker) GetValveActivityHistory(ctx context.Context, zoneID string, hours int) ([]ValveActivity, error) {
	return t.storage.GetValveActivityHistory(ctx, zoneID, hours)
}

// GetEnergyMetrics calculates energy consumption metrics
func (t *Tracker) GetEnergyMetrics(ctx context.Context, zoneID string, hours int) (*EnergyMetrics, error) {
	return t.metrics.CalculateEnergyMetrics(ctx, zoneID, hours)
}

// GetComfortMetrics calculates comfort metrics for a zone
func (t *Tracker) GetComfortMetrics(ctx context.Context, zoneID string, hours int) (*ComfortMetrics, error) {
	return t.metrics.CalculateComfortMetrics(ctx, zoneID, hours)
}

// GetSystemPerformanceMetrics retrieves system performance metrics
func (t *Tracker) GetSystemPerformanceMetrics(ctx context.Context, hours int) (*PerformanceMetrics, error) {
	return t.metrics.CalculatePerformanceMetrics(ctx, hours)
}

// GetAllZonesComfortSummary retrieves comfort summary for all zones
func (t *Tracker) GetAllZonesComfortSummary(ctx context.Context, hours int) (map[string]*ComfortMetrics, error) {
	// Get all zone IDs
	zoneKeys, err := t.redisClient.Keys(ctx, "multizone:zone:*")
	if err != nil {
		return nil, err
	}
	
	summary := make(map[string]*ComfortMetrics)
	for _, key := range zoneKeys {
		// Extract zone ID from key (multizone:zone:zoneID)
		zoneID := strings.TrimPrefix(key, "multizone:zone:")
		
		metrics, err := t.GetComfortMetrics(ctx, zoneID, hours)
		if err != nil {
			continue // Skip zones with errors
		}
		
		summary[zoneID] = metrics
	}
	
	return summary, nil
}

// TrackZoneUpdate tracks a zone state update
func (t *Tracker) TrackZoneUpdate(ctx context.Context, zone *models.ZoneState) error {
	timestamp := time.Now()
	
	// Record temperature
	if err := t.RecordTemperature(ctx, zone.ID, zone.CurrentTemperature, timestamp); err != nil {
		return err
	}
	
	// Record valve state
	if err := t.RecordValveActivity(ctx, zone.ID, zone.ValveState, timestamp); err != nil {
		return err
	}
	
	// Record satisfaction
	if err := t.RecordZoneSatisfaction(ctx, zone.ID, zone.Satisfaction, timestamp); err != nil {
		return err
	}
	
	return nil
}
