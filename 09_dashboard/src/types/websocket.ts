export type WebSocketConnectionStatus = "CONNECTING" | "LIVE" | "RECONNECTING" | "OFFLINE";

export interface WebSocketEventMessage<T = any> {
  event_type: string;
  timestamp: string;
  data: T;
}

export interface AlertCreatedPayload {
  alert_id: string;
  camera_id: string;
  registration: string;
  severity: string;
  match_score: number;
}

export interface SightingCreatedPayload {
  sighting_id: string;
  camera_id: string;
  registration: string;
  match_score: number;
  match_class: string;
}
