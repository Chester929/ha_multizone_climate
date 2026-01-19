export interface Zone {
  id: string;
  name: string;
  enabled: boolean;
  current_temperature?: string;
  target_temperature?: string;
  satisfaction?: string;
  valve_state?: string;
  priority?: number;
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
