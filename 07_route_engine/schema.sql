-- ==========================================================
-- SentinelTrack Priority 7 Database Schema
-- Camera Geolocation, Trajectory Analysis Runs & Route Segments
-- ==========================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Camera Schema Migrations (Idempotent)
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS azimuth DOUBLE PRECISION;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS location_quality TEXT DEFAULT 'UNKNOWN';
ALTER TABLE cameras ALTER COLUMN location_quality SET DEFAULT 'UNKNOWN';
UPDATE cameras
SET location_quality = 'UNKNOWN'
WHERE latitude IS NULL OR longitude IS NULL;

-- 2. Vehicle Sightings Schema Migrations (Idempotent)
ALTER TABLE vehicle_sightings ADD COLUMN IF NOT EXISTS event_time_utc TIMESTAMPTZ;
ALTER TABLE vehicle_sightings ADD COLUMN IF NOT EXISTS event_time_source TEXT DEFAULT 'DB_PERSISTENCE_FALLBACK';
ALTER TABLE vehicle_sightings ADD COLUMN IF NOT EXISTS event_time_quality TEXT DEFAULT 'LOW';
ALTER TABLE vehicle_sightings ADD COLUMN IF NOT EXISTS ingest_time_utc TIMESTAMPTZ;

-- 3. Route Analysis Runs Table
CREATE TABLE IF NOT EXISTS route_analysis_runs (
    route_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    registration TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    trajectory_confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    sighting_count INTEGER NOT NULL,
    total_distance_m DOUBLE PRECISION NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    geojson JSONB NOT NULL,
    warnings JSONB DEFAULT '[]'::jsonb,
    algorithm_version TEXT NOT NULL DEFAULT '1.0.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_route_runs_reg
ON route_analysis_runs(registration);

CREATE INDEX IF NOT EXISTS idx_route_runs_target_id
ON route_analysis_runs(target_id);

CREATE INDEX IF NOT EXISTS idx_route_runs_created_at
ON route_analysis_runs(created_at);


-- 4. Route Segments Table
CREATE TABLE IF NOT EXISTS route_segments (
    segment_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL REFERENCES route_analysis_runs(route_id) ON DELETE CASCADE,
    sequence_index INTEGER NOT NULL,
    from_sighting_id TEXT NOT NULL,
    to_sighting_id TEXT NOT NULL,
    from_camera_id TEXT NOT NULL,
    to_camera_id TEXT NOT NULL,
    distance_lower_bound_m DOUBLE PRECISION NOT NULL,
    delta_seconds DOUBLE PRECISION NOT NULL,
    minimum_required_speed_kmh DOUBLE PRECISION NOT NULL,
    feasibility TEXT NOT NULL,
    segment_score DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_route_segments_route_seq
ON route_segments(route_id, sequence_index);
