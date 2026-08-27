-- ==========================================================
-- SentinelTrack Priority 5 Database Schema
-- Watchlists, Vehicle Sightings, Target Matches & Alerts
-- ==========================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Watchlist Entries Table
CREATE TABLE IF NOT EXISTS watchlist_entries (
    watchlist_id TEXT PRIMARY KEY,
    registration TEXT NOT NULL,
    normalized_registration TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'NORMAL',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    notes TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_watchlist_norm_reg
ON watchlist_entries(normalized_registration);

CREATE INDEX IF NOT EXISTS idx_watchlist_enabled_priority
ON watchlist_entries(enabled, priority);


-- 2. Vehicle Sightings Table (Persists raw evidence for future rescoring)
CREATE TABLE IF NOT EXISTS vehicle_sightings (
    sighting_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    stream_epoch BIGINT NOT NULL DEFAULT 1,
    track_id BIGINT NOT NULL,
    first_pts_ms DOUBLE PRECISION NOT NULL,
    last_pts_ms DOUBLE PRECISION NOT NULL,
    registration_candidate TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    match_score DOUBLE PRECISION NOT NULL,
    match_class TEXT NOT NULL,
    target_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_evidence JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sightings_reg_candidate
ON vehicle_sightings(registration_candidate);

CREATE INDEX IF NOT EXISTS idx_sightings_camera_epoch_track
ON vehicle_sightings(camera_id, stream_epoch, track_id);

CREATE INDEX IF NOT EXISTS idx_sightings_created_at
ON vehicle_sightings(created_at);

CREATE INDEX IF NOT EXISTS idx_sightings_match_score
ON vehicle_sightings(match_score);


-- 3. Target Matches Table
CREATE TABLE IF NOT EXISTS target_matches (
    match_id TEXT PRIMARY KEY,
    sighting_id TEXT NOT NULL REFERENCES vehicle_sightings(sighting_id),
    watchlist_id TEXT NOT NULL REFERENCES watchlist_entries(watchlist_id),
    match_score DOUBLE PRECISION NOT NULL,
    match_class TEXT NOT NULL,
    raw_distance INTEGER NOT NULL,
    confusion_distance DOUBLE PRECISION NOT NULL,
    explanation JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_sighting_watchlist
ON target_matches(sighting_id, watchlist_id);

CREATE INDEX IF NOT EXISTS idx_matches_score_class
ON target_matches(match_score, match_class);


-- 4. Real-time Actionable Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    watchlist_id TEXT NOT NULL REFERENCES watchlist_entries(watchlist_id),
    sighting_id TEXT NOT NULL REFERENCES vehicle_sightings(sighting_id),
    camera_id TEXT NOT NULL,
    stream_epoch BIGINT NOT NULL,
    track_id BIGINT NOT NULL,
    registration TEXT NOT NULL,
    match_score DOUBLE PRECISION NOT NULL,
    match_class TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    explanation JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_alerts_ack_created
ON alerts(acknowledged, created_at);

CREATE INDEX IF NOT EXISTS idx_alerts_camera_track
ON alerts(camera_id, stream_epoch, track_id);
