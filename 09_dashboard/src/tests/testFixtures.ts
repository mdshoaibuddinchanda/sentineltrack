import { RouteResponse } from "../types/api";

/** Small deterministic fixture used only by component tests. */
export const TEST_ROUTE: RouteResponse = {
  target_id: "test-target",
  registration: "GJ01AB1234",
  status: "PLAUSIBLE_SEQUENCE",
  trajectory_confidence: 0.94,
  start_time_utc: "2026-01-01T10:00:00.000Z",
  end_time_utc: "2026-01-01T10:13:30.000Z",
  duration_seconds: 810,
  total_lower_bound_distance_m: 8420,
  minimum_average_speed_kmh: 37.4,
  sighting_count: 4,
  camera_count: 4,
  sightings: [
    { sighting_id: "s1", camera_id: "cam_vastrapur_01", event_time_utc: "2026-01-01T10:00:00.000Z", time_source: "SOURCE_WALLCLOCK", time_quality: "HIGH", latitude: 23.0354, longitude: 72.5292, location_quality: "VERIFIED", match_score: 0.94 },
    { sighting_id: "s2", camera_id: "cam_ashram_rd_01", event_time_utc: "2026-01-01T10:03:40.000Z", time_source: "SOURCE_WALLCLOCK", time_quality: "HIGH", latitude: 23.0415, longitude: 72.5714, location_quality: "VERIFIED", match_score: 0.95 },
    { sighting_id: "s3", camera_id: "cam_sg_highway_01", event_time_utc: "2026-01-01T10:07:00.000Z", time_source: "PTS_ANCHORED_ESTIMATE", time_quality: "MEDIUM", latitude: 23.0298, longitude: 72.5067, location_quality: "VERIFIED", match_score: 0.96 },
    { sighting_id: "s4", camera_id: "cam_sg_highway_02", event_time_utc: "2026-01-01T10:13:30.000Z", time_source: "SOURCE_WALLCLOCK", time_quality: "HIGH", latitude: 23.0489, longitude: 72.5184, location_quality: "VERIFIED", match_score: 0.98 },
  ],
  segments: [
    { segment_id: "seg1", sequence_index: 1, from_sighting_id: "s1", to_sighting_id: "s2", from_camera_id: "cam_vastrapur_01", to_camera_id: "cam_ashram_rd_01", distance_lower_bound_m: 4350, delta_seconds: 220, minimum_required_speed_kmh: 71.2, feasibility: "FEASIBLE", segment_score: 0.92, warnings: [] },
    { segment_id: "seg2", sequence_index: 2, from_sighting_id: "s2", to_sighting_id: "s3", from_camera_id: "cam_ashram_rd_01", to_camera_id: "cam_sg_highway_01", distance_lower_bound_m: 6720, delta_seconds: 200, minimum_required_speed_kmh: 121, feasibility: "QUESTIONABLE", segment_score: 0.78, warnings: ["High required transit speed"] },
    { segment_id: "seg3", sequence_index: 3, from_sighting_id: "s3", to_sighting_id: "s4", from_camera_id: "cam_sg_highway_01", to_camera_id: "cam_sg_highway_02", distance_lower_bound_m: 2450, delta_seconds: 390, minimum_required_speed_kmh: 22.6, feasibility: "FEASIBLE", segment_score: 0.97, warnings: [] },
  ],
  alternative_trajectories_count: 0,
  reasons: ["Chronological continuity verified"],
  warnings: ["One segment is questionable under straight-line assumptions"],
  disclaimer: "Test fixture only.",
};
