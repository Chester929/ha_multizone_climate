package models

import "time"

// ZoneState represents the state of a heating zone
type ZoneState struct {
	ID                      string    `json:"id"`
	Name                    string    `json:"name"`
	Enabled                 bool      `json:"enabled"`
	TemperatureSensorEntity string    `json:"temperature_sensor_entity_id"`
	ValveSwitchEntity       string    `json:"valve_switch_entity_id"`
	CurrentTemperature      float64   `json:"current_temperature"`
	TargetTemperature       float64   `json:"target_temperature"`
	Satisfaction            string    `json:"satisfaction"` // "underheated", "satisfied", "overheated"
	ValveState              string    `json:"valve_state"`  // "open", "closed"
	TemperatureRising       bool      `json:"temperature_rising"`
	TemperatureFalling      bool      `json:"temperature_falling"`
	TargetChangeThreshold   float64   `json:"target_change_threshold"`
	OpeningOffset           float64   `json:"opening_offset"`
	ClosingOffset           float64   `json:"closing_offset"`
	IsFallbackValve         bool       `json:"is_fallback_valve"`
	Priority                int        `json:"priority"`
	LastUpdated             time.Time  `json:"last_updated"`
	LastActuated            *time.Time `json:"last_actuated,omitempty"`
	ValveLockExpiration     *time.Time `json:"valve_lock_expiration,omitempty"`
}

// MainClimateState represents the main HVAC thermostat state
type MainClimateState struct {
	EntityID           string    `json:"entity_id"`
	CurrentTemperature float64   `json:"current_temperature"`
	TargetTemperature  float64   `json:"target_temperature"`
	OutdoorTemperature float64   `json:"outdoor_temperature"`
	HVACMode           string    `json:"hvac_mode"`
	HVACAction         string    `json:"hvac_action"`
	MultizoneEnabled   bool      `json:"multizone_enabled"`
	LastUpdated        time.Time `json:"last_updated"`
}

// GlobalConfig represents the global system configuration
type GlobalConfig struct {
	MainClimateEntityID         string  `json:"main_climate_entity_id"`
	MainTargetAllZonesSatisfied float64 `json:"main_target_all_zones_satisfied"`
	UseAverageMode              bool    `json:"use_average_mode"`
	SliderPosition              float64 `json:"slider_position"` // 0.0 to 1.0, used when UseAverageMode is false
	MinValvesOpen               int     `json:"min_valves_open"`
	MainMinTemp                 float64 `json:"main_min_temp"`
	MainMaxTemp                 float64 `json:"main_max_temp"`
	MainChangeThreshold         float64 `json:"main_change_threshold"`
	ValveActuationDelay         int     `json:"valve_actuation_delay"`
	CoordinatorInterval         int     `json:"coordinator_interval"`
	SatisfactionEpsilon         float64 `json:"satisfaction_eps"`
}

// Job represents a background job
type Job struct {
	ID        string                 `json:"id"`
	Type      string                 `json:"type"`
	Timestamp time.Time              `json:"timestamp"`
	Params    map[string]interface{} `json:"params"`
}

// JobStatus represents the status of a job
type JobStatus struct {
	JobID       string                 `json:"job_id"`
	JobType     string                 `json:"job_type"`
	Status      string                 `json:"status"` // "pending", "running", "completed", "failed"
	StartedAt   time.Time              `json:"started_at"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`
	DurationMs  int64                  `json:"duration_ms"`
	Result      map[string]interface{} `json:"result,omitempty"`
	Error       string                 `json:"error,omitempty"`
}
