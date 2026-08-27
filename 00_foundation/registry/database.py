import os
import json
import psycopg

from dotenv import load_dotenv


load_dotenv()


def get_connection():

    return psycopg.connect(

        host=os.getenv(
            "DATABASE_HOST",
            "localhost",
        ),

        port=os.getenv(
            "DATABASE_PORT",
            "5432",
        ),

        dbname=os.getenv(
            "DATABASE_NAME",
            "sentinel",
        ),

        user=os.getenv(
            "DATABASE_USER",
            "sentinel",
        ),

        password=os.getenv(
            "DATABASE_PASSWORD",
        ),
    )


def upsert_camera(camera):

    sql = """
    INSERT INTO cameras (
        camera_id,
        name,
        department,
        latitude,
        longitude,
        location,
        codec,
        width,
        height,
        reported_fps,
        bitrate,
        live,
        rtsp_url,
        webrtc_url,
        hls_url,
        raw_metadata,
        updated_at
    )

    VALUES (
        %(camera_id)s,
        %(name)s,
        %(department)s,
        %(latitude)s,
        %(longitude)s,

        CASE
            WHEN %(latitude)s::double precision IS NOT NULL
             AND %(longitude)s::double precision IS NOT NULL
            THEN ST_SetSRID(
                ST_MakePoint(
                    %(longitude)s::double precision,
                    %(latitude)s::double precision
                ),
                4326
            )::geography
            ELSE NULL
        END,


        %(codec)s,
        %(width)s,
        %(height)s,
        %(reported_fps)s,
        %(bitrate)s,
        %(live)s,
        %(rtsp_url)s,
        %(webrtc_url)s,
        %(hls_url)s,
        %(raw_metadata)s::jsonb,
        NOW()
    )

    ON CONFLICT (camera_id)

    DO UPDATE SET

        name = EXCLUDED.name,
        department = EXCLUDED.department,

        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,

        location = EXCLUDED.location,

        codec = EXCLUDED.codec,

        width = EXCLUDED.width,
        height = EXCLUDED.height,

        reported_fps = EXCLUDED.reported_fps,

        bitrate = EXCLUDED.bitrate,

        live = EXCLUDED.live,

        rtsp_url = EXCLUDED.rtsp_url,

        webrtc_url = EXCLUDED.webrtc_url,

        hls_url = EXCLUDED.hls_url,

        raw_metadata = EXCLUDED.raw_metadata,

        updated_at = NOW();
    """

    params = camera.model_dump()

    params["raw_metadata"] = json.dumps(
        params["raw_metadata"]
    )

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                sql,
                params,
            )


def get_all_cameras() -> list[dict]:
    """Fetch all camera records from the registry."""
    query = """
    SELECT
        camera_id, name, department, latitude, longitude,
        codec, width, height, reported_fps, measured_fps, bitrate, live,
        rtsp_url, webrtc_url, hls_url, stream_status,
        first_frame_latency_ms, last_pts_ms, last_checked,
        raw_metadata, updated_at
    FROM cameras
    ORDER BY camera_id ASC;
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query)
            return cur.fetchall()


def get_camera(camera_id: str) -> dict | None:
    """Fetch a single camera record by camera_id."""
    query = """
    SELECT
        camera_id, name, department, latitude, longitude,
        codec, width, height, reported_fps, measured_fps, bitrate, live,
        rtsp_url, webrtc_url, hls_url, stream_status,
        first_frame_latency_ms, last_pts_ms, last_checked,
        raw_metadata, updated_at
    FROM cameras
    WHERE camera_id = %(camera_id)s;
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, {"camera_id": camera_id})
            return cur.fetchone()


def update_camera_probe_status(
    camera_id: str,
    stream_status: str,
    codec: str | None = None,
    width: int | None = None,
    height: int | None = None,
    measured_fps: float | None = None,
    first_frame_latency_ms: float | None = None,
) -> None:
    """Update camera probe results and stream health status."""
    query = """
    UPDATE cameras
    SET
        stream_status = %(stream_status)s,
        codec = COALESCE(%(codec)s, codec),
        width = COALESCE(%(width)s, width),
        height = COALESCE(%(height)s, height),
        measured_fps = COALESCE(%(measured_fps)s, measured_fps),
        first_frame_latency_ms = COALESCE(%(first_frame_latency_ms)s, first_frame_latency_ms),
        last_checked = NOW(),
        updated_at = NOW()
    WHERE camera_id = %(camera_id)s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "camera_id": camera_id,
                    "stream_status": stream_status,
                    "codec": codec,
                    "width": width,
                    "height": height,
                    "measured_fps": measured_fps,
                    "first_frame_latency_ms": first_frame_latency_ms,
                },
            )


def record_health_event(
    camera_id: str,
    event_type: str,
    message: str,
    pts_ms: float | None = None,
) -> None:
    """Insert a health or stream event into camera_health_events."""
    query = """
    INSERT INTO camera_health_events (
        camera_id, event_type, message, pts_ms, created_at
    )
    VALUES (
        %(camera_id)s, %(event_type)s, %(message)s, %(pts_ms)s, NOW()
    );
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "camera_id": camera_id,
                    "event_type": event_type,
                    "message": message,
                    "pts_ms": pts_ms,
                },
            )


def get_health_events(camera_id: str | None = None, limit: int = 50) -> list[dict]:
    """Fetch recent health events for a specific camera or all cameras."""
    if camera_id:
        query = """
        SELECT id, camera_id, event_type, message, pts_ms, created_at
        FROM camera_health_events
        WHERE camera_id = %(camera_id)s
        ORDER BY created_at DESC
        LIMIT %(limit)s;
        """
        params = {"camera_id": camera_id, "limit": limit}
    else:
        query = """
        SELECT id, camera_id, event_type, message, pts_ms, created_at
        FROM camera_health_events
        ORDER BY created_at DESC
        LIMIT %(limit)s;
        """
        params = {"limit": limit}

    with get_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()