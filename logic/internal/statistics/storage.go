package statistics

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/chester929/ha_multizone_climate/logic/internal/logger"
	"github.com/chester929/ha_multizone_climate/logic/internal/redis"
)

// Storage handles Redis storage for statistics
type Storage struct {
	redisClient *redis.Client
}

// TemperatureReading represents a temperature reading at a point in time
type TemperatureReading struct {
	ZoneID      string    `json:"zone_id"`
	Temperature float64   `json:"temperature"`
	Timestamp   time.Time `json:"timestamp"`
}

// ValveActivity represents a valve state change
type ValveActivity struct {
	ZoneID    string    `json:"zone_id"`
	State     string    `json:"state"` // "open" or "closed"
	Timestamp time.Time `json:"timestamp"`
}

// ZoneSatisfaction represents zone satisfaction at a point in time
type ZoneSatisfaction struct {
	ZoneID       string    `json:"zone_id"`
	Satisfaction string    `json:"satisfaction"` // "underheated", "satisfied", "overheated"
	Timestamp    time.Time `json:"timestamp"`
}

// AlgorithmExecution represents an algorithm execution record
type AlgorithmExecution struct {
	AlgorithmType string    `json:"algorithm_type"`
	DurationMs    int64     `json:"duration_ms"`
	Timestamp     time.Time `json:"timestamp"`
}

// NewStorage creates a new storage instance
func NewStorage(redisClient *redis.Client) *Storage {
	return &Storage{
		redisClient: redisClient,
	}
}

// StoreTemperatureReading stores a temperature reading in Redis
func (s *Storage) StoreTemperatureReading(ctx context.Context, zoneID string, temperature float64, timestamp time.Time) error {
	reading := TemperatureReading{
		ZoneID:      zoneID,
		Temperature: temperature,
		Timestamp:   timestamp,
	}
	
	data, err := json.Marshal(reading)
	if err != nil {
		return err
	}
	
	key := fmt.Sprintf("multizone:stats:temp:%s", zoneID)
	
	// Store in hash with timestamp as field key
	// Note: For large datasets, consider using sorted sets (ZADD) for more efficient time-based queries
	return s.redisClient.HSet(ctx, key, map[string]interface{}{
		fmt.Sprintf("%d", timestamp.Unix()): string(data),
	})
}

// GetTemperatureHistory retrieves temperature history for a zone
func (s *Storage) GetTemperatureHistory(ctx context.Context, zoneID string, hours int) ([]TemperatureReading, error) {
	key := fmt.Sprintf("multizone:stats:temp:%s", zoneID)
	
	// Get all readings
	// Note: This loads all data and filters in-memory. For production with large datasets,
	// consider using sorted sets (ZRANGEBYSCORE) or implementing TTL-based expiration
	data, err := s.redisClient.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}
	
	cutoffTime := time.Now().Add(-time.Duration(hours) * time.Hour)
	readings := []TemperatureReading{}
	
	for _, value := range data {
		var reading TemperatureReading
		if err := json.Unmarshal([]byte(value), &reading); err != nil {
			logger.Debug("Failed to unmarshal temperature reading: %v", err)
			continue
		}
		
		if reading.Timestamp.After(cutoffTime) {
			readings = append(readings, reading)
		}
	}
	
	return readings, nil
}

// StoreValveActivity stores valve activity in Redis
func (s *Storage) StoreValveActivity(ctx context.Context, zoneID string, state string, timestamp time.Time) error {
	activity := ValveActivity{
		ZoneID:    zoneID,
		State:     state,
		Timestamp: timestamp,
	}
	
	data, err := json.Marshal(activity)
	if err != nil {
		return err
	}
	
	key := fmt.Sprintf("multizone:stats:valve:%s", zoneID)
	
	return s.redisClient.HSet(ctx, key, map[string]interface{}{
		fmt.Sprintf("%d", timestamp.Unix()): string(data),
	})
}

// GetValveActivityHistory retrieves valve activity history for a zone
func (s *Storage) GetValveActivityHistory(ctx context.Context, zoneID string, hours int) ([]ValveActivity, error) {
	key := fmt.Sprintf("multizone:stats:valve:%s", zoneID)
	
	data, err := s.redisClient.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}
	
	cutoffTime := time.Now().Add(-time.Duration(hours) * time.Hour)
	activities := []ValveActivity{}
	
	for _, value := range data {
		var activity ValveActivity
		if err := json.Unmarshal([]byte(value), &activity); err != nil {
			logger.Debug("Failed to unmarshal valve activity: %v", err)
			continue
		}
		
		if activity.Timestamp.After(cutoffTime) {
			activities = append(activities, activity)
		}
	}
	
	return activities, nil
}

// StoreZoneSatisfaction stores zone satisfaction in Redis
func (s *Storage) StoreZoneSatisfaction(ctx context.Context, zoneID string, satisfaction string, timestamp time.Time) error {
	satisfactionData := ZoneSatisfaction{
		ZoneID:       zoneID,
		Satisfaction: satisfaction,
		Timestamp:    timestamp,
	}
	
	data, err := json.Marshal(satisfactionData)
	if err != nil {
		return err
	}
	
	key := fmt.Sprintf("multizone:stats:satisfaction:%s", zoneID)
	
	return s.redisClient.HSet(ctx, key, map[string]interface{}{
		fmt.Sprintf("%d", timestamp.Unix()): string(data),
	})
}

// GetZoneSatisfactionHistory retrieves zone satisfaction history
func (s *Storage) GetZoneSatisfactionHistory(ctx context.Context, zoneID string, hours int) ([]ZoneSatisfaction, error) {
	key := fmt.Sprintf("multizone:stats:satisfaction:%s", zoneID)
	
	data, err := s.redisClient.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}
	
	cutoffTime := time.Now().Add(-time.Duration(hours) * time.Hour)
	satisfactions := []ZoneSatisfaction{}
	
	for _, value := range data {
		var satisfaction ZoneSatisfaction
		if err := json.Unmarshal([]byte(value), &satisfaction); err != nil {
			logger.Debug("Failed to unmarshal zone satisfaction: %v", err)
			continue
		}
		
		if satisfaction.Timestamp.After(cutoffTime) {
			satisfactions = append(satisfactions, satisfaction)
		}
	}
	
	return satisfactions, nil
}

// StoreAlgorithmExecution stores algorithm execution metrics
func (s *Storage) StoreAlgorithmExecution(ctx context.Context, algorithmType string, durationMs int64, timestamp time.Time) error {
	execution := AlgorithmExecution{
		AlgorithmType: algorithmType,
		DurationMs:    durationMs,
		Timestamp:     timestamp,
	}
	
	data, err := json.Marshal(execution)
	if err != nil {
		return err
	}
	
	key := fmt.Sprintf("multizone:stats:algorithm:%s", algorithmType)
	
	return s.redisClient.HSet(ctx, key, map[string]interface{}{
		fmt.Sprintf("%d", timestamp.Unix()): string(data),
	})
}

// GetAlgorithmExecutionHistory retrieves algorithm execution history
func (s *Storage) GetAlgorithmExecutionHistory(ctx context.Context, algorithmType string, hours int) ([]AlgorithmExecution, error) {
	key := fmt.Sprintf("multizone:stats:algorithm:%s", algorithmType)
	
	data, err := s.redisClient.HGetAll(ctx, key)
	if err != nil {
		return nil, err
	}
	
	cutoffTime := time.Now().Add(-time.Duration(hours) * time.Hour)
	executions := []AlgorithmExecution{}
	
	for _, value := range data {
		var execution AlgorithmExecution
		if err := json.Unmarshal([]byte(value), &execution); err != nil {
			logger.Debug("Failed to unmarshal algorithm execution: %v", err)
			continue
		}
		
		if execution.Timestamp.After(cutoffTime) {
			executions = append(executions, execution)
		}
	}
	
	return executions, nil
}
