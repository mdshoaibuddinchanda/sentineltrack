import os
import json
import sqlite3
import threading
import importlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, Any

from .models import (
    WatchlistEntry,
    WatchlistPriority,
    Sighting,
    TargetMatchRecord,
    MatchClass,
    Alert,
    AlertSeverity
)
from .config import TargetMatchingConfig



class BaseTargetMatchingRepository(ABC):
    """Abstract data repository interface for Target Matching persistence."""

    @abstractmethod
    def save_watchlist_entry(self, entry: WatchlistEntry) -> None:
        pass

    @abstractmethod
    def get_watchlist_entry(self, watchlist_id: str) -> Optional[WatchlistEntry]:
        pass

    @abstractmethod
    def list_active_watchlist_entries(self) -> list[WatchlistEntry]:
        pass

    @abstractmethod
    def save_sighting(self, sighting: Sighting) -> None:
        pass

    @abstractmethod
    def save_target_match(self, match: TargetMatchRecord) -> None:
        pass

    @abstractmethod
    def save_alert(self, alert: Alert) -> None:
        pass

    @abstractmethod
    def query_sightings(
        self,
        registration_pattern: Optional[str] = None,
        camera_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def query_target_matches(
        self,
        sighting_id: Optional[str] = None,
        watchlist_id: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def query_alerts(
        self,
        unacknowledged_only: bool = False,
        camera_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        pass


class SQLiteTargetMatchingRepository(BaseTargetMatchingRepository):
    """SQLite / in-memory resilient implementation for isolated testing."""

    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS watchlist_entries (
                    watchlist_id TEXT PRIMARY KEY,
                    registration TEXT NOT NULL,
                    normalized_registration TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    notes TEXT,
                    metadata TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS vehicle_sightings (
                    sighting_id TEXT PRIMARY KEY,
                    camera_id TEXT NOT NULL,
                    stream_epoch INTEGER NOT NULL,
                    track_id INTEGER NOT NULL,
                    first_pts_ms REAL NOT NULL,
                    last_pts_ms REAL NOT NULL,
                    registration_candidate TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    match_score REAL NOT NULL,
                    match_class TEXT NOT NULL,
                    target_id TEXT,
                    created_at TEXT NOT NULL,
                    raw_evidence TEXT,
                    event_time_utc TEXT,
                    event_time_source TEXT,
                    event_time_quality TEXT,
                    ingest_time_utc TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS target_matches (
                    match_id TEXT PRIMARY KEY,
                    sighting_id TEXT NOT NULL,
                    watchlist_id TEXT NOT NULL,
                    match_score REAL NOT NULL,
                    match_class TEXT NOT NULL,
                    raw_distance INTEGER NOT NULL,
                    confusion_distance REAL NOT NULL,
                    matched_from TEXT NOT NULL,
                    alternative_rank INTEGER NOT NULL,
                    explanation TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    watchlist_id TEXT NOT NULL,
                    sighting_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    stream_epoch INTEGER NOT NULL,
                    track_id INTEGER NOT NULL,
                    registration TEXT NOT NULL,
                    match_score REAL NOT NULL,
                    match_class TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    explanation TEXT
                )
            ''')
            self._conn.commit()

    def save_watchlist_entry(self, entry: WatchlistEntry) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO watchlist_entries 
                (watchlist_id, registration, normalized_registration, priority, enabled, created_at, expires_at, notes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.watchlist_id,
                entry.registration,
                entry.normalized_registration,
                entry.priority.value if hasattr(entry.priority, 'value') else str(entry.priority),
                1 if entry.enabled else 0,
                entry.created_at.isoformat(),
                entry.expires_at.isoformat() if entry.expires_at else None,
                entry.notes,
                json.dumps(entry.metadata)
            ))
            self._conn.commit()

    def get_watchlist_entry(self, watchlist_id: str) -> Optional[WatchlistEntry]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('SELECT * FROM watchlist_entries WHERE watchlist_id = ?', (watchlist_id,))
            row = cur.fetchone()
            if not row:
                return None
            return WatchlistEntry(
                watchlist_id=row['watchlist_id'],
                registration=row['registration'],
                normalized_registration=row['normalized_registration'],
                priority=WatchlistPriority(row['priority']),
                enabled=bool(row['enabled']),
                created_at=datetime.fromisoformat(row['created_at']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                notes=row['notes'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            )

    def list_active_watchlist_entries(self) -> list[WatchlistEntry]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('SELECT * FROM watchlist_entries WHERE enabled = 1')
            rows = cur.fetchall()
            entries = []
            now = datetime.now(timezone.utc)
            for row in rows:
                exp = datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None
                if exp and exp < now:
                    continue
                entries.append(WatchlistEntry(
                    watchlist_id=row['watchlist_id'],
                    registration=row['registration'],
                    normalized_registration=row['normalized_registration'],
                    priority=WatchlistPriority(row['priority']),
                    enabled=bool(row['enabled']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    expires_at=exp,
                    notes=row['notes'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                ))
            return entries

    def save_sighting(self, sighting: Sighting) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO vehicle_sightings
                (sighting_id, camera_id, stream_epoch, track_id, first_pts_ms, last_pts_ms, registration_candidate, confidence, match_score, match_class, target_id, created_at, raw_evidence, event_time_utc, event_time_source, event_time_quality, ingest_time_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sighting.sighting_id,
                sighting.camera_id,
                sighting.stream_epoch,
                sighting.track_id,
                sighting.first_pts_ms,
                sighting.last_pts_ms,
                sighting.registration_candidate,
                sighting.confidence,
                sighting.match_score,
                sighting.match_class.value if hasattr(sighting.match_class, 'value') else str(sighting.match_class),
                sighting.target_id,
                sighting.created_at.isoformat(),
                json.dumps(sighting.raw_evidence),
                sighting.event_time_utc.isoformat() if sighting.event_time_utc else None,
                sighting.event_time_source,
                sighting.event_time_quality,
                sighting.ingest_time_utc.isoformat() if sighting.ingest_time_utc else None
            ))
            self._conn.commit()

    def save_target_match(self, match: TargetMatchRecord) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO target_matches
                (match_id, sighting_id, watchlist_id, match_score, match_class, raw_distance, confusion_distance, matched_from, alternative_rank, explanation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match.match_id,
                match.sighting_id,
                match.watchlist_id,
                match.match_score,
                match.match_class.value if hasattr(match.match_class, 'value') else str(match.match_class),
                match.raw_distance,
                match.confusion_distance,
                match.matched_from,
                match.alternative_rank,
                json.dumps(match.explanation),
                match.created_at.isoformat()
            ))
            self._conn.commit()

    def save_alert(self, alert: Alert) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO alerts
                (alert_id, watchlist_id, sighting_id, camera_id, stream_epoch, track_id, registration, match_score, match_class, severity, created_at, acknowledged, acknowledged_by, acknowledged_at, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.alert_id,
                alert.watchlist_id,
                alert.sighting_id,
                alert.camera_id,
                alert.stream_epoch,
                alert.track_id,
                alert.registration,
                alert.match_score,
                alert.match_class.value if hasattr(alert.match_class, 'value') else str(alert.match_class),
                alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
                alert.created_at.isoformat(),
                1 if alert.acknowledged else 0,
                alert.acknowledged_by,
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                json.dumps(alert.explanation)
            ))
            self._conn.commit()

    def query_sightings(
        self,
        registration_pattern: Optional[str] = None,
        camera_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            query = ['SELECT * FROM vehicle_sightings WHERE match_score >= ?']
            params = [min_score]

            if camera_id:
                query.append('AND camera_id = ?')
                params.append(camera_id)

            if created_after:
                query.append('AND created_at >= ?')
                params.append(created_after.isoformat())

            if created_before:
                query.append('AND created_at <= ?')
                params.append(created_before.isoformat())

            if registration_pattern:
                sql_pat = registration_pattern.replace('*', '%').replace('?', '_')
                query.append('AND registration_candidate LIKE ?')
                params.append(sql_pat)

            query.append('ORDER BY COALESCE(event_time_utc, created_at) DESC LIMIT ?')
            params.append(limit)

            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def query_target_matches(
        self,
        sighting_id: Optional[str] = None,
        watchlist_id: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            query = ['SELECT * FROM target_matches WHERE match_score >= ?']
            params = [min_score]

            if sighting_id:
                query.append('AND sighting_id = ?')
                params.append(sighting_id)

            if watchlist_id:
                query.append('AND watchlist_id = ?')
                params.append(watchlist_id)

            query.append('ORDER BY match_score DESC LIMIT ?')
            params.append(limit)

            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def query_alerts(
        self,
        unacknowledged_only: bool = False,
        camera_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            query = ['SELECT * FROM alerts WHERE 1=1']
            params = []

            if unacknowledged_only:
                query.append('AND acknowledged = 0')

            if camera_id:
                query.append('AND camera_id = ?')
                params.append(camera_id)

            query.append('ORDER BY created_at DESC LIMIT ?')
            params.append(limit)

            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]


# Backwards compatibility alias
TargetMatchingRepository = SQLiteTargetMatchingRepository


class PostgresTargetMatchingRepository(BaseTargetMatchingRepository):
    """Production PostgreSQL/PostGIS repository connecting via psycopg."""

    def __init__(self):
        self._get_connection = importlib.import_module('00_foundation.registry.database').get_connection
        self._ensure_schema()

    def _ensure_schema(self):
        try:
            conn = self._get_connection()
            schema_path = Path(__file__).resolve().parent / 'schema.sql'
            if schema_path.exists():
                sql = schema_path.read_text(encoding='utf-8')
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            conn.close()
        except Exception:
            pass

    def save_watchlist_entry(self, entry: WatchlistEntry) -> None:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO watchlist_entries 
                (watchlist_id, registration, normalized_registration, priority, enabled, created_at, expires_at, notes, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (watchlist_id) DO UPDATE SET
                    registration = EXCLUDED.registration,
                    normalized_registration = EXCLUDED.normalized_registration,
                    priority = EXCLUDED.priority,
                    enabled = EXCLUDED.enabled,
                    expires_at = EXCLUDED.expires_at,
                    notes = EXCLUDED.notes,
                    metadata = EXCLUDED.metadata;
            ''', (
                entry.watchlist_id,
                entry.registration,
                entry.normalized_registration,
                entry.priority.value if hasattr(entry.priority, 'value') else str(entry.priority),
                entry.enabled,
                entry.created_at,
                entry.expires_at,
                entry.notes,
                json.dumps(entry.metadata)
            ))
        conn.commit()
        conn.close()

    def get_watchlist_entry(self, watchlist_id: str) -> Optional[WatchlistEntry]:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT watchlist_id, registration, normalized_registration, priority, enabled, created_at, expires_at, notes, metadata FROM watchlist_entries WHERE watchlist_id = %s', (watchlist_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            entry = WatchlistEntry(
                watchlist_id=row[0],
                registration=row[1],
                normalized_registration=row[2],
                priority=WatchlistPriority(row[3]),
                enabled=bool(row[4]),
                created_at=row[5],
                expires_at=row[6],
                notes=row[7],
                metadata=row[8] if isinstance(row[8], dict) else (json.loads(row[8]) if row[8] else {})
            )
        conn.close()
        return entry

    def list_active_watchlist_entries(self) -> list[WatchlistEntry]:
        conn = self._get_connection()
        entries = []
        with conn.cursor() as cur:
            cur.execute('''
                SELECT watchlist_id, registration, normalized_registration, priority, enabled, created_at, expires_at, notes, metadata
                FROM watchlist_entries
                WHERE enabled = TRUE AND (expires_at IS NULL OR expires_at >= NOW())
            ''')
            rows = cur.fetchall()
            for r in rows:
                entries.append(WatchlistEntry(
                    watchlist_id=r[0],
                    registration=r[1],
                    normalized_registration=r[2],
                    priority=WatchlistPriority(r[3]),
                    enabled=bool(r[4]),
                    created_at=r[5],
                    expires_at=r[6],
                    notes=r[7],
                    metadata=r[8] if isinstance(r[8], dict) else (json.loads(r[8]) if r[8] else {})
                ))
        conn.close()
        return entries

    def save_sighting(self, sighting: Sighting) -> None:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO vehicle_sightings
                (sighting_id, camera_id, stream_epoch, track_id, first_pts_ms, last_pts_ms, registration_candidate, confidence, match_score, match_class, target_id, created_at, raw_evidence, event_time_utc, event_time_source, event_time_quality, ingest_time_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sighting_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    match_class = EXCLUDED.match_class,
                    raw_evidence = EXCLUDED.raw_evidence,
                    event_time_utc = EXCLUDED.event_time_utc,
                    event_time_source = EXCLUDED.event_time_source,
                    event_time_quality = EXCLUDED.event_time_quality,
                    ingest_time_utc = EXCLUDED.ingest_time_utc;
            ''', (
                sighting.sighting_id,
                sighting.camera_id,
                sighting.stream_epoch,
                sighting.track_id,
                sighting.first_pts_ms,
                sighting.last_pts_ms,
                sighting.registration_candidate,
                sighting.confidence,
                sighting.match_score,
                sighting.match_class.value if hasattr(sighting.match_class, 'value') else str(sighting.match_class),
                sighting.target_id,
                sighting.created_at,
                json.dumps(sighting.raw_evidence),
                sighting.event_time_utc,
                sighting.event_time_source,
                sighting.event_time_quality,
                sighting.ingest_time_utc
            ))
        conn.commit()
        conn.close()

    def save_target_match(self, match: TargetMatchRecord) -> None:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO target_matches
                (match_id, sighting_id, watchlist_id, match_score, match_class, raw_distance, confusion_distance, explanation, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    match_class = EXCLUDED.match_class,
                    explanation = EXCLUDED.explanation;
            ''', (
                match.match_id,
                match.sighting_id,
                match.watchlist_id,
                match.match_score,
                match.match_class.value if hasattr(match.match_class, 'value') else str(match.match_class),
                match.raw_distance,
                match.confusion_distance,
                json.dumps(match.explanation),
                match.created_at
            ))
        conn.commit()
        conn.close()

    def save_alert(self, alert: Alert) -> None:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO alerts
                (alert_id, watchlist_id, sighting_id, camera_id, stream_epoch, track_id, registration, match_score, match_class, severity, created_at, acknowledged, acknowledged_by, acknowledged_at, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (alert_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    match_class = EXCLUDED.match_class,
                    severity = EXCLUDED.severity,
                    acknowledged = EXCLUDED.acknowledged,
                    acknowledged_by = EXCLUDED.acknowledged_by,
                    acknowledged_at = EXCLUDED.acknowledged_at,
                    explanation = EXCLUDED.explanation;
            ''', (
                alert.alert_id,
                alert.watchlist_id,
                alert.sighting_id,
                alert.camera_id,
                alert.stream_epoch,
                alert.track_id,
                alert.registration,
                alert.match_score,
                alert.match_class.value if hasattr(alert.match_class, 'value') else str(alert.match_class),
                alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
                alert.created_at,
                alert.acknowledged,
                alert.acknowledged_by,
                alert.acknowledged_at,
                json.dumps(alert.explanation)
            ))
        conn.commit()
        conn.close()

    def query_sightings(
        self,
        registration_pattern: Optional[str] = None,
        camera_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        query = ['SELECT sighting_id, camera_id, stream_epoch, track_id, first_pts_ms, last_pts_ms, registration_candidate, confidence, match_score, match_class, target_id, created_at, raw_evidence, event_time_utc, event_time_source, event_time_quality, ingest_time_utc FROM vehicle_sightings WHERE match_score >= %s']
        params = [min_score]

        if camera_id:
            query.append('AND camera_id = %s')
            params.append(camera_id)

        if created_after:
            query.append('AND COALESCE(event_time_utc, created_at) >= %s')
            params.append(created_after)

        if created_before:
            query.append('AND COALESCE(event_time_utc, created_at) <= %s')
            params.append(created_before)

        if registration_pattern:
            sql_pat = registration_pattern.replace('*', '%').replace('?', '_')
            query.append('AND registration_candidate LIKE %s')
            params.append(sql_pat)

        query.append('ORDER BY COALESCE(event_time_utc, created_at) DESC LIMIT %s')
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    'sighting_id': r[0],
                    'camera_id': r[1],
                    'stream_epoch': r[2],
                    'track_id': r[3],
                    'first_pts_ms': r[4],
                    'last_pts_ms': r[5],
                    'registration_candidate': r[6],
                    'confidence': r[7],
                    'match_score': r[8],
                    'match_class': r[9],
                    'target_id': r[10],
                    'created_at': r[11].isoformat() if hasattr(r[11], 'isoformat') else str(r[11]),
                    'raw_evidence': r[12] if isinstance(r[12], dict) else (json.loads(r[12]) if r[12] else {}),
                    'event_time_utc': r[13].isoformat() if hasattr(r[13], 'isoformat') and r[13] else (str(r[13]) if r[13] else None),
                    'event_time_source': r[14],
                    'event_time_quality': r[15],
                    'ingest_time_utc': r[16].isoformat() if hasattr(r[16], 'isoformat') and r[16] else (str(r[16]) if r[16] else None)
                })
        conn.close()
        return results

    def query_target_matches(
        self,
        sighting_id: Optional[str] = None,
        watchlist_id: Optional[str] = None,
        min_score: float = 0.0,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        query = ['SELECT match_id, sighting_id, watchlist_id, match_score, match_class, raw_distance, confusion_distance, explanation, created_at FROM target_matches WHERE match_score >= %s']
        params = [min_score]

        if sighting_id:
            query.append('AND sighting_id = %s')
            params.append(sighting_id)

        if watchlist_id:
            query.append('AND watchlist_id = %s')
            params.append(watchlist_id)

        query.append('ORDER BY match_score DESC LIMIT %s')
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    'match_id': r[0],
                    'sighting_id': r[1],
                    'watchlist_id': r[2],
                    'match_score': r[3],
                    'match_class': r[4],
                    'raw_distance': r[5],
                    'confusion_distance': r[6],
                    'explanation': r[7] if isinstance(r[7], list) else (json.loads(r[7]) if r[7] else []),
                    'created_at': r[8].isoformat() if hasattr(r[8], 'isoformat') else str(r[8])
                })
        conn.close()
        return results

    def query_alerts(
        self,
        unacknowledged_only: bool = False,
        camera_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        query = ['SELECT alert_id, watchlist_id, sighting_id, camera_id, stream_epoch, track_id, registration, match_score, match_class, severity, created_at, acknowledged, acknowledged_by, acknowledged_at, explanation FROM alerts WHERE 1=1']
        params = []

        if unacknowledged_only:
            query.append('AND acknowledged = FALSE')

        if camera_id:
            query.append('AND camera_id = %s')
            params.append(camera_id)

        query.append('ORDER BY created_at DESC LIMIT %s')
        params.append(limit)

        with conn.cursor() as cur:
            cur.execute(' '.join(query), params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    'alert_id': r[0],
                    'watchlist_id': r[1],
                    'sighting_id': r[2],
                    'camera_id': r[3],
                    'stream_epoch': r[4],
                    'track_id': r[5],
                    'registration': r[6],
                    'match_score': r[7],
                    'match_class': r[8],
                    'severity': r[9],
                    'created_at': r[10].isoformat() if hasattr(r[10], 'isoformat') else str(r[10]),
                    'acknowledged': bool(r[11]),
                    'acknowledged_by': r[12],
                    'acknowledged_at': r[13].isoformat() if r[13] else None,
                    'explanation': r[14] if isinstance(r[14], list) else (json.loads(r[14]) if r[14] else [])
                })
        conn.close()
        return results


def get_repository(config: Optional[TargetMatchingConfig] = None) -> BaseTargetMatchingRepository:
    """Factory creating appropriate repository according to config."""
    cfg = config or TargetMatchingConfig.from_yaml()
    if cfg.db_backend == 'postgres':
        try:
            return PostgresTargetMatchingRepository()
        except Exception:
            return SQLiteTargetMatchingRepository(db_path=cfg.sqlite_db_path)
    return SQLiteTargetMatchingRepository(db_path=cfg.sqlite_db_path)
