import os
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from .models import (
    WatchlistEntry,
    WatchlistPriority,
    Sighting,
    MatchClass,
    Alert,
    AlertSeverity
)


class TargetMatchingRepository:
    """
    Data repository for SentinelTrack Priority 5.
    Persists watchlists, sightings, matches, and alerts.
    Supports PostgreSQL if available, and resilient SQLite/in-memory store for isolated unit tests/offline PoC.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or ':memory:'
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_sqlite_schema()

    def _init_sqlite_schema(self):
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
                    raw_evidence TEXT
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

    def save_watchlist_entry(self, entry: WatchlistEntry):
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

    def save_sighting(self, sighting: Sighting):
        with self._lock:
            cur = self._conn.cursor()
            cur.execute('''
                INSERT OR REPLACE INTO vehicle_sightings
                (sighting_id, camera_id, stream_epoch, track_id, first_pts_ms, last_pts_ms, registration_candidate, confidence, match_score, match_class, target_id, created_at, raw_evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(sighting.raw_evidence)
            ))
            self._conn.commit()

    def save_alert(self, alert: Alert):
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

            if registration_pattern:
                # Handle SQL LIKE patterns
                sql_pat = registration_pattern.replace('*', '%').replace('?', '_')
                query.append('AND registration_candidate LIKE ?')
                params.append(sql_pat)

            query.append('ORDER BY created_at DESC LIMIT ?')
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
