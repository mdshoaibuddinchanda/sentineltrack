CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,

    name TEXT,
    department TEXT,

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    location GEOGRAPHY(POINT, 4326),

    codec TEXT,

    width INTEGER,
    height INTEGER,

    reported_fps DOUBLE PRECISION,
    measured_fps DOUBLE PRECISION,

    bitrate BIGINT,

    live BOOLEAN,

    rtsp_url TEXT,
    webrtc_url TEXT,
    hls_url TEXT,

    stream_status TEXT DEFAULT 'UNKNOWN',

    first_frame_latency_ms DOUBLE PRECISION,

    last_pts_ms DOUBLE PRECISION,

    last_checked TIMESTAMPTZ,

    raw_metadata JSONB,

    updated_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_cameras_location
ON cameras
USING GIST(location);


CREATE TABLE IF NOT EXISTS camera_health_events (
    id BIGSERIAL PRIMARY KEY,

    camera_id TEXT REFERENCES cameras(camera_id),

    event_type TEXT,

    message TEXT,

    pts_ms DOUBLE PRECISION,

    created_at TIMESTAMPTZ DEFAULT NOW()
);