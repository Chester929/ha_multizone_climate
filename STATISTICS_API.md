# Statistics and Metrics API

This document describes the Statistics and Metrics API endpoints added to the multizone climate control system.

## Overview

The Statistics and Metrics feature tracks and provides historical data about:
- Temperature readings over time
- Valve activity and state changes
- Energy consumption estimates
- Comfort metrics for zones
- System performance metrics

## API Endpoints

### Temperature History

**GET** `/api/statistics/zones/{id}/temperature?hours=24`

Returns temperature history for a specific zone.

**Query Parameters:**
- `hours` (optional): Number of hours of history to retrieve (default: 24)

**Response:**
```json
{
  "zone_id": "living_room",
  "hours": 24,
  "count": 48,
  "data": [
    {
      "zone_id": "living_room",
      "temperature": 21.5,
      "timestamp": "2026-01-20T10:00:00Z"
    }
  ]
}
```

### Valve Activity History

**GET** `/api/statistics/zones/{id}/valve-activity?hours=24`

Returns valve state change history for a specific zone.

**Query Parameters:**
- `hours` (optional): Number of hours of history to retrieve (default: 24)

**Response:**
```json
{
  "zone_id": "living_room",
  "hours": 24,
  "count": 12,
  "data": [
    {
      "zone_id": "living_room",
      "state": "open",
      "timestamp": "2026-01-20T10:00:00Z"
    }
  ]
}
```

### Energy Metrics

**GET** `/api/statistics/zones/{id}/energy?hours=24`

Returns energy consumption metrics for a specific zone.

**Query Parameters:**
- `hours` (optional): Number of hours for metrics calculation (default: 24)

**Response:**
```json
{
  "zone_id": "living_room",
  "total_runtime_hours": 8.5,
  "open_percentage": 35.4,
  "estimated_energy_kwh": 0.85,
  "cycle_count": 12,
  "average_open_time_minutes": 42.5,
  "time_range_hours": 24
}
```

### Comfort Metrics

**GET** `/api/statistics/zones/{id}/comfort?hours=24`

Returns comfort metrics for a specific zone.

**Query Parameters:**
- `hours` (optional): Number of hours for metrics calculation (default: 24)

**Response:**
```json
{
  "zone_id": "living_room",
  "satisfied_percentage": 85.5,
  "underheated_percentage": 10.0,
  "overheated_percentage": 4.5,
  "average_temperature": 21.2,
  "temperature_std_dev": 0.8,
  "comfort_score": 88.5,
  "time_range_hours": 24
}
```

### All Zones Comfort Summary

**GET** `/api/statistics/comfort-summary?hours=24`

Returns comfort metrics for all zones.

**Query Parameters:**
- `hours` (optional): Number of hours for metrics calculation (default: 24)

**Response:**
```json
{
  "hours": 24,
  "zones": {
    "living_room": {
      "zone_id": "living_room",
      "satisfied_percentage": 85.5,
      "comfort_score": 88.5,
      ...
    },
    "bedroom": {
      "zone_id": "bedroom",
      "satisfied_percentage": 92.0,
      "comfort_score": 94.0,
      ...
    }
  }
}
```

### System Performance Metrics

**GET** `/api/statistics/performance?hours=24`

Returns system performance metrics including algorithm execution times.

**Query Parameters:**
- `hours` (optional): Number of hours for metrics calculation (default: 24)

**Response:**
```json
{
  "temp_calculation_avg_ms": 15.5,
  "valve_update_avg_ms": 8.2,
  "safety_check_avg_ms": 5.1,
  "temp_calculation_count": 100,
  "valve_update_count": 50,
  "safety_check_count": 25,
  "total_executions": 175,
  "time_range_hours": 24
}
```

## How Statistics are Tracked

Statistics are automatically tracked during normal system operation:

1. **Temperature History**: Recorded every time a zone state is updated
2. **Valve Activity**: Recorded when valves are opened or closed
3. **Zone Satisfaction**: Recorded during valve update operations
4. **Algorithm Execution**: Recorded for each algorithm execution (calculate_temp, update_valves, safety_check)

## Data Storage

All statistics are stored in Redis using the following key patterns:

- `multizone:stats:temp:{zone_id}` - Temperature history
- `multizone:stats:valve:{zone_id}` - Valve activity history
- `multizone:stats:satisfaction:{zone_id}` - Zone satisfaction history
- `multizone:stats:algorithm:{algorithm_type}` - Algorithm execution metrics

## Metrics Calculations

### Energy Consumption

Energy consumption is estimated based on:
- Valve runtime (total hours valves were open)
- Assumed power consumption of 100W per valve
- Formula: `Energy (kWh) = Runtime (hours) × 0.1 kW`

### Comfort Score

Comfort score (0-100) is calculated using:
- **70% weight**: Zone satisfaction percentage
- **30% weight**: Temperature stability (lower standard deviation = higher score)

### Performance Metrics

Performance metrics track:
- Average execution time for each algorithm type
- Total number of executions
- Helps identify performance bottlenecks

## Usage Examples

### Get 48 hours of temperature history
```bash
curl http://localhost:8080/api/statistics/zones/living_room/temperature?hours=48
```

### Get today's energy consumption
```bash
curl http://localhost:8080/api/statistics/zones/bedroom/energy?hours=24
```

### Get comfort summary for all zones
```bash
curl http://localhost:8080/api/statistics/comfort-summary?hours=24
```

### Monitor system performance
```bash
curl http://localhost:8080/api/statistics/performance?hours=24
```
