export interface Zone {
  id: string;
  name: string;
  enabled: boolean;
  temperature_sensor_entity_id?: string;
  valve_switch_entity_id?: string;
  climate_entity_id?: string;
  current_temperature?: string;
  target_temperature?: string;
  satisfaction?: string;
  valve_state?: string;
  priority?: number;
  target_change_threshold?: number;
  opening_offset?: number;
  closing_offset?: number;
  is_fallback_valve?: boolean;
}

export interface Config {
  main_target_temperature?: string;
  mode?: string;
  [key: string]: string | undefined;
}

export interface HistoricalDataPoint {
  timestamp: string;
  current_temperature?: string;
  target_temperature?: string;
  valve_state?: string;
  satisfaction?: string;
}

export interface SystemStatus {
  status: string;
  redis: string;
  time: string;
}

export interface WebSocketMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}
