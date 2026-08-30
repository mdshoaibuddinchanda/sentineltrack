export type TargetPriority = "CRITICAL" | "HIGH" | "NORMAL" | "LOW";
export type MatchClass = "EXACT" | "HIGH_PROBABILITY" | "PROBABLE" | "POSSIBLE";
export type AlertSeverity = "CRITICAL" | "HIGH" | "NORMAL" | "LOW";
export type FeasibilityClass = "FEASIBLE" | "QUESTIONABLE" | "IMPOSSIBLE" | "UNKNOWN";
export type TrajectoryStatus = "PLAUSIBLE_SEQUENCE" | "AMBIGUOUS" | "CONFLICTING_SIGHTINGS" | "SINGLE_SIGHTING" | "NO_ROUTE";
export type TimeQuality = "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
export type LocationQuality = "VERIFIED" | "APPROXIMATE" | "UNKNOWN";
export type CameraStreamStatus = "ONLINE" | "DEGRADED" | "OFFLINE" | "UNKNOWN";

export interface Camera {
  camera_id: string;
  name?: string;
  department?: string;
  latitude?: number | null;
  longitude?: number | null;
  azimuth?: number;
  location_quality: LocationQuality;
  live: boolean;
  stream_status: CameraStreamStatus;
  measured_fps?: number;
  last_checked?: string;
  metadata?: Record<string, any>;
}

export interface CameraListResponse {
  items: Camera[];
  total: number;
}

export interface CameraHealth {
  camera_id: string;
  stream_status: CameraStreamStatus;
  first_frame_latency_ms?: number;
  last_pts_ms?: number;
  last_checked?: string;
}

export interface Target {
  target_id: string;
  registration: string;
  normalized_registration: string;
  priority: TargetPriority;
  enabled: boolean;
  created_at: string;
  expires_at?: string;
  notes?: string;
  metadata?: Record<string, any>;
}

export interface TargetListResponse {
  items: Target[];
  total: number;
}

export interface TargetCreateRequest {
  registration: string;
  priority?: TargetPriority;
  expires_at?: string;
  notes?: string;
  metadata?: Record<string, any>;
}

export interface TargetUpdateRequest {
  priority?: TargetPriority;
  enabled?: boolean;
  expires_at?: string;
  notes?: string;
  metadata?: Record<string, any>;
}

export interface Sighting {
  sighting_id: string;
  camera_id: string;
  stream_epoch: number;
  track_id: number;
  first_pts_ms: number;
  last_pts_ms: number;
  registration_candidate: string;
  confidence: number;
  match_score: number;
  match_class: MatchClass;
  target_id?: string;
  created_at: string;
  raw_evidence?: Record<string, any>;
  event_time_utc?: string;
  event_time_source?: string;
  event_time_quality?: TimeQuality;
  ingest_time_utc?: string;
}

export interface SightingListResponse {
  items: Sighting[];
  total: number;
}

export interface VehicleHistoryResponse {
  registration: string;
  normalized_registration: string;
  total_sightings: number;
  sightings: Sighting[];
}

export interface Alert {
  alert_id: string;
  watchlist_id: string;
  sighting_id: string;
  camera_id: string;
  stream_epoch: number;
  track_id: number;
  registration: string;
  match_score: number;
  match_class: MatchClass;
  severity: AlertSeverity;
  created_at: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  explanation: string[];
}

export interface AlertListResponse {
  items: Alert[];
  total: number;
  unacknowledged_count: number;
}

export interface AlertAckRequest {
  acknowledged_by: string;
}

export interface AlertAckResponse {
  success: boolean;
  alert_id: string;
  acknowledged: boolean;
  acknowledged_by: string;
  acknowledged_at: string;
}

export interface RouteSegment {
  segment_id: string;
  sequence_index: number;
  from_sighting_id: string;
  to_sighting_id: string;
  from_camera_id: string;
  to_camera_id: string;
  distance_lower_bound_m: number;
  delta_seconds: number;
  minimum_required_speed_kmh: number;
  feasibility: FeasibilityClass;
  segment_score: number;
  warnings: string[];
}

export interface RouteSighting {
  sighting_id: string;
  camera_id: string;
  event_time_utc: string;
  time_source: string;
  time_quality: TimeQuality;
  latitude?: number | null;
  longitude?: number | null;
  location_quality: LocationQuality;
  match_score: number;
}

export interface RouteResponse {
  target_id: string;
  registration: string;
  status: TrajectoryStatus;
  trajectory_confidence: number;
  start_time_utc?: string;
  end_time_utc?: string;
  duration_seconds: number;
  total_lower_bound_distance_m: number;
  minimum_average_speed_kmh: number;
  sighting_count: number;
  camera_count: number;
  sightings: RouteSighting[];
  segments: RouteSegment[];
  alternative_trajectories_count: number;
  reasons: string[];
  warnings: string[];
  disclaimer: string;
}

export interface RouteSummaryResponse {
  registration: string;
  status: TrajectoryStatus;
  confidence: number;
  total_distance_km: number;
  duration_minutes: number;
  avg_speed_kmh: number;
  sighting_count: number;
  camera_count: number;
  reasons: string[];
  warnings: string[];
  disclaimer: string;
}

export interface GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Point" | "LineString";
    coordinates: number[] | number[][];
  };
  properties: Record<string, any>;
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  features: GeoJSONFeature[];
  properties: Record<string, any>;
}

export interface HealthResponse {
  status: "healthy" | "unhealthy";
  version: string;
  git_sha: string;
  uptime_seconds: number;
}

export interface ReadinessResponse {
  status: "ready" | "degraded" | "unhealthy";
  components: {
    database: boolean;
    postgis: boolean;
    camera_registry: boolean;
    target_repository: boolean;
    route_engine: boolean;
    analytics_worker?: boolean;
    vehicle_detector?: boolean;
    tracker?: boolean;
    plate_detector?: boolean;
    ocr_pipeline?: boolean;
    target_pipeline?: boolean;
    [key: string]: boolean | undefined;
  };
  details: Record<string, any>;
}

export interface MetricsSnapshot {
  total_requests: number;
  active_ws_clients: number;
  active_camera_workers: number;
  total_frames_ingested: number;
  total_frames_dropped: number;
  total_vehicle_detections: number;
  total_plate_inferences: number;
  total_ocr_inferences: number;
  total_sightings_persisted: number;
  total_alerts_generated: number;
  total_routes_generated: number;
  uptime_seconds: number;
}

export interface MetricsResponse {
  metrics: MetricsSnapshot;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: any;
  };
}
