import os
import json
import time
import queue
import logging
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
import psycopg
from psycopg import rows

try:
    from dotenv import load_dotenv
    if os.getenv("SENTINEL_ENV", "development").lower() != "production":
        load_dotenv()
except ImportError:
    pass



logger = logging.getLogger("sentineltrack.database")


class PooledConnectionWrapper:
    """Wraps a psycopg connection, intercepting close() / context manager to return to pool."""

    def __init__(self, conn, pool: Optional["BoundedConnectionPool"] = None):
        self._conn = conn
        self._pool = pool
        self._returned = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self._conn.rollback()
            except Exception:
                pass
        else:
            try:
                if not getattr(self._conn, "autocommit", False):
                    self._conn.commit()
            except Exception:
                pass
        self.close()

    def close(self):
        if not self._returned:
            self._returned = True
            if self._pool:
                self._pool.return_connection(self._conn)
            else:
                try:
                    self._conn.close()
                except Exception:
                    pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _get_db_password() -> str:
    """
    Safely retrieves database password with strict production fail-closed semantics.
    """
    env_name = os.getenv("SENTINEL_ENV", "development").lower()
    password = os.getenv("DATABASE_PASSWORD")
    if not password:
        if env_name == "production":
            raise RuntimeError("DATABASE_PASSWORD is required in production environment (fail-closed).")
        return "sentinel_password"
    return password


class BoundedConnectionPool:
    """Thread-safe bounded connection pool with health validation, reuse and telemetry."""

    def __init__(
        self,
        min_size: int = 2,
        max_size: int = 10,
        timeout_s: float = 2.0
    ):
        self.min_size = min_size
        self.max_size = max_size
        self.timeout_s = timeout_s

        self._pool: queue.Queue = queue.Queue(maxsize=max_size)
        self._active_connections = 0
        self._lock = threading.Lock()
        self._total_created = 0
        self._total_timeouts = 0
        self._total_errors = 0

    def _create_raw_connection(self):
        conn = psycopg.connect(
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
            dbname=os.getenv("DATABASE_NAME", "sentinel"),
            user=os.getenv("DATABASE_USER", "sentinel"),
            password=_get_db_password(),
        )
        self._total_created += 1
        return conn




    def get_connection(self, timeout: Optional[float] = None) -> PooledConnectionWrapper:
        t_out = timeout if timeout is not None else self.timeout_s
        conn = None

        # 1. Try to get existing idle connection
        try:
            conn = self._pool.get_nowait()
        except queue.Empty:
            # 2. If pool is empty, check if we can create a new connection up to max_size
            with self._lock:
                if self._active_connections < self.max_size:
                    self._active_connections += 1
                    try:
                        conn = self._create_raw_connection()
                    except Exception as e:
                        self._active_connections -= 1
                        self._total_errors += 1
                        raise e

        # 3. If at max capacity, wait for available connection with timeout; fallback to ephemeral on timeout
        if conn is None:
            try:
                conn = self._pool.get(block=True, timeout=t_out)
            except queue.Empty:
                self._total_timeouts += 1
                logger.warning(f"Connection pool exhausted (active={self._active_connections}); creating ephemeral connection.")
                try:
                    conn = self._create_raw_connection()
                    return PooledConnectionWrapper(conn, None)
                except Exception as e:
                    self._total_errors += 1
                    raise e

        # 4. Validate connection health
        is_healthy = False
        try:
            if not conn.closed:
                is_healthy = True
        except Exception:
            is_healthy = False

        if not is_healthy:
            try:
                conn.close()
            except Exception:
                pass
            conn = self._create_raw_connection()

        return PooledConnectionWrapper(conn, self)

    def return_connection(self, conn) -> None:
        if conn.closed:
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)
            return

        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            idle = self._pool.qsize()
            in_use = max(0, self._active_connections - idle)
            return {
                "max_size": self.max_size,
                "active_connections": self._active_connections,
                "in_use": in_use,
                "idle": idle,
                "total_created": self._total_created,
                "total_timeouts": self._total_timeouts,
                "total_errors": self._total_errors
            }


_GLOBAL_DB_POOL: Optional[BoundedConnectionPool] = None
_POOL_LOCK = threading.Lock()


def get_db_pool() -> BoundedConnectionPool:
    global _GLOBAL_DB_POOL
    with _POOL_LOCK:
        if _GLOBAL_DB_POOL is None:
            min_s = int(os.getenv("SENTINEL_DB_POOL_MIN", "2"))
            max_s = int(os.getenv("SENTINEL_DB_POOL_MAX", "10"))
            timeout_s = float(os.getenv("SENTINEL_DB_POOL_TIMEOUT", "0.5"))
            _GLOBAL_DB_POOL = BoundedConnectionPool(min_size=min_s, max_size=max_s, timeout_s=timeout_s)
        return _GLOBAL_DB_POOL


def get_pooled_connection(timeout: Optional[float] = None) -> PooledConnectionWrapper:
    """Returns a connection from the bounded connection pool."""
    return get_db_pool().get_connection(timeout=timeout)


def get_connection(autocommit: bool = False) -> psycopg.Connection:
    """
    Returns a direct PostgreSQL database connection.
    Preserves exact backwards compatibility for legacy repository modules.
    """
    host = os.getenv("DATABASE_HOST", "localhost")
    port = int(os.getenv("DATABASE_PORT", "5432"))
    dbname = os.getenv("DATABASE_NAME", "sentinel")
    user = os.getenv("DATABASE_USER", "sentinel")
    password = _get_db_password()
    conn = psycopg.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        autocommit=autocommit,
    )
    return conn



@contextmanager
def db_connection() -> Generator[PooledConnectionWrapper, None, None]:
    """Context manager for automatic connection checkout and check-in from pool."""
    conn = get_pooled_connection()
    try:
        yield conn
    finally:
        conn.close()



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