package statistics

import (
	"context"
	"sort"
	"time"
)

// MetricsCalculator calculates various statistics metrics
type MetricsCalculator struct {
	storage *Storage
}

// EnergyMetrics represents energy consumption metrics
type EnergyMetrics struct {
	ZoneID             string  `json:"zone_id"`
	TotalRuntimeHours  float64 `json:"total_runtime_hours"`
	OpenPercentage     float64 `json:"open_percentage"`
	EstimatedEnergyKWh float64 `json:"estimated_energy_kwh"`
	CycleCount         int     `json:"cycle_count"`
	AverageOpenTime    float64 `json:"average_open_time_minutes"`
	TimeRange          int     `json:"time_range_hours"`
}

// ComfortMetrics represents comfort metrics for a zone
type ComfortMetrics struct {
	ZoneID                 string  `json:"zone_id"`
	SatisfiedPercentage    float64 `json:"satisfied_percentage"`
	UnderheatedPercentage  float64 `json:"underheated_percentage"`
	OverheatedPercentage   float64 `json:"overheated_percentage"`
	AverageTemperature     float64 `json:"average_temperature"`
	TemperatureStdDev      float64 `json:"temperature_std_dev"`
	ComfortScore           float64 `json:"comfort_score"` // 0-100, higher is better
	TimeRange              int     `json:"time_range_hours"`
}

// PerformanceMetrics represents system performance metrics
type PerformanceMetrics struct {
	TempCalculationAvgMs   float64 `json:"temp_calculation_avg_ms"`
	ValveUpdateAvgMs       float64 `json:"valve_update_avg_ms"`
	SafetyCheckAvgMs       float64 `json:"safety_check_avg_ms"`
	TempCalculationCount   int     `json:"temp_calculation_count"`
	ValveUpdateCount       int     `json:"valve_update_count"`
	SafetyCheckCount       int     `json:"safety_check_count"`
	TotalExecutions        int     `json:"total_executions"`
	TimeRange              int     `json:"time_range_hours"`
}

// NewMetricsCalculator creates a new metrics calculator
func NewMetricsCalculator(storage *Storage) *MetricsCalculator {
	return &MetricsCalculator{
		storage: storage,
	}
}

// CalculateEnergyMetrics calculates energy consumption metrics for a zone
func (m *MetricsCalculator) CalculateEnergyMetrics(ctx context.Context, zoneID string, hours int) (*EnergyMetrics, error) {
	// Get valve activity history
	activities, err := m.storage.GetValveActivityHistory(ctx, zoneID, hours)
	if err != nil {
		return nil, err
	}
	
	if len(activities) == 0 {
		return &EnergyMetrics{
			ZoneID:    zoneID,
			TimeRange: hours,
		}, nil
	}
	
	// Sort activities by timestamp
	sort.Slice(activities, func(i, j int) bool {
		return activities[i].Timestamp.Before(activities[j].Timestamp)
	})
	
	var totalRuntimeSeconds float64
	var cycleCount int
	var openTimes []float64
	
	var lastOpenTime *time.Time
	
	for i, activity := range activities {
		if activity.State == "open" {
			lastOpenTime = &activity.Timestamp
			cycleCount++
		} else if activity.State == "closed" && lastOpenTime != nil {
			// Calculate runtime for this cycle
			runtime := activity.Timestamp.Sub(*lastOpenTime).Seconds()
			totalRuntimeSeconds += runtime
			openTimes = append(openTimes, runtime/60) // Convert to minutes
			lastOpenTime = nil
		}
		
		// If this is the last activity and valve is still open
		if i == len(activities)-1 && activity.State == "open" {
			runtime := time.Now().Sub(activity.Timestamp).Seconds()
			totalRuntimeSeconds += runtime
			openTimes = append(openTimes, runtime/60)
		}
	}
	
	totalRuntimeHours := totalRuntimeSeconds / 3600
	totalPeriodHours := float64(hours)
	openPercentage := (totalRuntimeHours / totalPeriodHours) * 100
	
	// Estimate energy consumption (assuming 100W per valve when open)
	estimatedEnergyKWh := totalRuntimeHours * 0.1 // 100W = 0.1kW
	
	// Calculate average open time
	var averageOpenTime float64
	if len(openTimes) > 0 {
		sum := 0.0
		for _, t := range openTimes {
			sum += t
		}
		averageOpenTime = sum / float64(len(openTimes))
	}
	
	return &EnergyMetrics{
		ZoneID:             zoneID,
		TotalRuntimeHours:  totalRuntimeHours,
		OpenPercentage:     openPercentage,
		EstimatedEnergyKWh: estimatedEnergyKWh,
		CycleCount:         cycleCount,
		AverageOpenTime:    averageOpenTime,
		TimeRange:          hours,
	}, nil
}

// CalculateComfortMetrics calculates comfort metrics for a zone
func (m *MetricsCalculator) CalculateComfortMetrics(ctx context.Context, zoneID string, hours int) (*ComfortMetrics, error) {
	// Get satisfaction history
	satisfactions, err := m.storage.GetZoneSatisfactionHistory(ctx, zoneID, hours)
	if err != nil {
		return nil, err
	}
	
	// Get temperature history
	temperatures, err := m.storage.GetTemperatureHistory(ctx, zoneID, hours)
	if err != nil {
		return nil, err
	}
	
	metrics := &ComfortMetrics{
		ZoneID:    zoneID,
		TimeRange: hours,
	}
	
	// Calculate satisfaction percentages
	if len(satisfactions) > 0 {
		satisfiedCount := 0
		underheatedCount := 0
		overheatedCount := 0
		
		for _, s := range satisfactions {
			switch s.Satisfaction {
			case "satisfied":
				satisfiedCount++
			case "underheated":
				underheatedCount++
			case "overheated":
				overheatedCount++
			}
		}
		
		total := float64(len(satisfactions))
		metrics.SatisfiedPercentage = (float64(satisfiedCount) / total) * 100
		metrics.UnderheatedPercentage = (float64(underheatedCount) / total) * 100
		metrics.OverheatedPercentage = (float64(overheatedCount) / total) * 100
	}
	
	// Calculate temperature statistics
	if len(temperatures) > 0 {
		sum := 0.0
		for _, t := range temperatures {
			sum += t.Temperature
		}
		metrics.AverageTemperature = sum / float64(len(temperatures))
		
		// Calculate standard deviation
		varianceSum := 0.0
		for _, t := range temperatures {
			diff := t.Temperature - metrics.AverageTemperature
			varianceSum += diff * diff
		}
		variance := varianceSum / float64(len(temperatures))
		
		// Simple square root approximation using Newton's method
		// For better accuracy, consider importing "math" package and using math.Sqrt(variance)
		if variance > 0 {
			x := variance
			for i := 0; i < 10; i++ {
				x = (x + variance/x) / 2
			}
			metrics.TemperatureStdDev = x
		}
	}
	
	// Calculate comfort score (0-100)
	// Higher satisfaction percentage = higher score
	// Lower temperature variance = higher score
	satisfactionWeight := 0.7
	stabilityWeight := 0.3
	
	satisfactionScore := metrics.SatisfiedPercentage
	
	// Stability score based on temperature std dev
	// Lower std dev = more stable = higher score
	// Assume std dev > 2.0 is poor, 0 is perfect
	stabilityScore := 100.0
	if metrics.TemperatureStdDev > 0 {
		stabilityScore = 100.0 - (metrics.TemperatureStdDev * 25.0)
		if stabilityScore < 0 {
			stabilityScore = 0
		}
	}
	
	metrics.ComfortScore = (satisfactionScore * satisfactionWeight) + (stabilityScore * stabilityWeight)
	
	return metrics, nil
}

// CalculatePerformanceMetrics calculates system performance metrics
func (m *MetricsCalculator) CalculatePerformanceMetrics(ctx context.Context, hours int) (*PerformanceMetrics, error) {
	metrics := &PerformanceMetrics{
		TimeRange: hours,
	}
	
	// Get execution history for each algorithm type
	tempCalcs, err := m.storage.GetAlgorithmExecutionHistory(ctx, "calculate_temp", hours)
	if err == nil && len(tempCalcs) > 0 {
		sum := int64(0)
		for _, exec := range tempCalcs {
			sum += exec.DurationMs
		}
		metrics.TempCalculationAvgMs = float64(sum) / float64(len(tempCalcs))
		metrics.TempCalculationCount = len(tempCalcs)
	}
	
	valveUpdates, err := m.storage.GetAlgorithmExecutionHistory(ctx, "update_valves", hours)
	if err == nil && len(valveUpdates) > 0 {
		sum := int64(0)
		for _, exec := range valveUpdates {
			sum += exec.DurationMs
		}
		metrics.ValveUpdateAvgMs = float64(sum) / float64(len(valveUpdates))
		metrics.ValveUpdateCount = len(valveUpdates)
	}
	
	safetyChecks, err := m.storage.GetAlgorithmExecutionHistory(ctx, "safety_check", hours)
	if err == nil && len(safetyChecks) > 0 {
		sum := int64(0)
		for _, exec := range safetyChecks {
			sum += exec.DurationMs
		}
		metrics.SafetyCheckAvgMs = float64(sum) / float64(len(safetyChecks))
		metrics.SafetyCheckCount = len(safetyChecks)
	}
	
	metrics.TotalExecutions = metrics.TempCalculationCount + metrics.ValveUpdateCount + metrics.SafetyCheckCount
	
	return metrics, nil
}
