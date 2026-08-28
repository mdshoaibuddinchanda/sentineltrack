import os
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .models import User, UserRole, Session, AuditEvent


def _parse_iso(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    try:
        dt = datetime.fromisoformat(str(val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _format_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class BaseSecurityRepository(ABC):
    """Abstract data access interface for SentinelTrack security entities."""

    # Users
    @abstractmethod
    def save_user(self, user: User) -> None:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[User]:
        pass

    @abstractmethod
    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        pass

    @abstractmethod
    def count_users(self) -> int:
        pass

    @abstractmethod
    def update_user(self, user: User) -> None:
        pass

    @abstractmethod
    def count_active_admins(self) -> int:
        pass

    # Sessions
    @abstractmethod
    def save_session(self, session: Session) -> None:
        pass

    @abstractmethod
    def get_session_by_token_hash(self, token_hash: str) -> Optional[Session]:
        pass

    @abstractmethod
    def update_session_activity(self, session_id: str, last_seen_at: datetime, idle_expires_at: datetime) -> None:
        pass

    @abstractmethod
    def revoke_session(self, session_id: str) -> None:
        pass

    @abstractmethod
    def revoke_all_user_sessions(self, user_id: str) -> int:
        pass

    @abstractmethod
    def cleanup_expired_sessions(self) -> int:
        pass

    # Audit Trail (Append-Only)
    @abstractmethod
    def save_audit_event(self, event: AuditEvent) -> None:
        pass

    @abstractmethod
    def query_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditEvent]:
        pass

    @abstractmethod
    def count_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        pass


class SqliteSecurityRepository(BaseSecurityRepository):
    """Thread-safe SQLite / in-memory implementation for isolated tests & local mock."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS security_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    must_change_password INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT,
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS security_sessions (
                    session_id TEXT PRIMARY KEY,
                    session_token_hash TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    idle_expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    csrf_token_hash TEXT NOT NULL,
                    revoked_at TEXT,
                    source_ip TEXT,
                    user_agent_hash TEXT,
                    FOREIGN KEY (user_id) REFERENCES security_users(user_id)
                );
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS security_audit_events (
                    audit_id TEXT PRIMARY KEY,
                    event_time_utc TEXT NOT NULL,
                    actor_user_id TEXT,
                    actor_username TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    outcome TEXT NOT NULL,
                    request_id TEXT,
                    source_ip TEXT,
                    user_agent TEXT,
                    details_json TEXT DEFAULT '{}'
                );
            """)

    def save_user(self, user: User) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                INSERT INTO security_users (
                    user_id, username, display_name, password_hash, role,
                    enabled, must_change_password, created_at, updated_at,
                    last_login_at, failed_login_count, locked_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    display_name=excluded.display_name,
                    password_hash=excluded.password_hash,
                    role=excluded.role,
                    enabled=excluded.enabled,
                    must_change_password=excluded.must_change_password,
                    updated_at=excluded.updated_at,
                    last_login_at=excluded.last_login_at,
                    failed_login_count=excluded.failed_login_count,
                    locked_until=excluded.locked_until;
            """, (
                user.user_id,
                user.username.strip().lower(),
                user.display_name,
                user.password_hash,
                user.role.value if isinstance(user.role, UserRole) else str(user.role),
                1 if user.enabled else 0,
                1 if user.must_change_password else 0,
                _format_iso(user.created_at),
                _format_iso(user.updated_at),
                _format_iso(user.last_login_at),
                user.failed_login_count,
                _format_iso(user.locked_until)
            ))

    def _row_to_user(self, r: sqlite3.Row) -> User:
        return User(
            user_id=r["user_id"],
            username=r["username"],
            display_name=r["display_name"],
            password_hash=r["password_hash"],
            role=UserRole(r["role"]),
            enabled=bool(r["enabled"]),
            must_change_password=bool(r["must_change_password"]),
            created_at=_parse_iso(r["created_at"]) or datetime.now(timezone.utc),
            updated_at=_parse_iso(r["updated_at"]) or datetime.now(timezone.utc),
            last_login_at=_parse_iso(r["last_login_at"]),
            failed_login_count=r["failed_login_count"],
            locked_until=_parse_iso(r["locked_until"])
        )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM security_users WHERE user_id = ?;", (user_id,))
            r = cur.fetchone()
            return self._row_to_user(r) if r else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM security_users WHERE username = ?;",
                (username.strip().lower(),)
            )
            r = cur.fetchone()
            return self._row_to_user(r) if r else None

    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM security_users ORDER BY created_at ASC LIMIT ? OFFSET ?;",
                (limit, offset)
            )
            return [self._row_to_user(r) for r in cur.fetchall()]

    def count_users(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM security_users;")
            return cur.fetchone()[0]

    def update_user(self, user: User) -> None:
        self.save_user(user)

    def count_active_admins(self) -> int:
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM security_users WHERE role = 'ADMIN' AND enabled = 1;"
            )
            return cur.fetchone()[0]

    def save_session(self, session: Session) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                INSERT INTO security_sessions (
                    session_id, session_token_hash, user_id, created_at,
                    last_seen_at, idle_expires_at, absolute_expires_at,
                    csrf_token_hash, revoked_at, source_ip, user_agent_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at,
                    idle_expires_at=excluded.idle_expires_at,
                    revoked_at=excluded.revoked_at;
            """, (
                session.session_id,
                session.session_token_hash,
                session.user_id,
                _format_iso(session.created_at),
                _format_iso(session.last_seen_at),
                _format_iso(session.idle_expires_at),
                _format_iso(session.absolute_expires_at),
                session.csrf_token_hash,
                _format_iso(session.revoked_at),
                session.source_ip,
                session.user_agent_hash
            ))

    def _row_to_session(self, r: sqlite3.Row) -> Session:
        return Session(
            session_id=r["session_id"],
            session_token_hash=r["session_token_hash"],
            user_id=r["user_id"],
            created_at=_parse_iso(r["created_at"]) or datetime.now(timezone.utc),
            last_seen_at=_parse_iso(r["last_seen_at"]) or datetime.now(timezone.utc),
            idle_expires_at=_parse_iso(r["idle_expires_at"]) or datetime.now(timezone.utc),
            absolute_expires_at=_parse_iso(r["absolute_expires_at"]) or datetime.now(timezone.utc),
            csrf_token_hash=r["csrf_token_hash"],
            revoked_at=_parse_iso(r["revoked_at"]),
            source_ip=r["source_ip"],
            user_agent_hash=r["user_agent_hash"]
        )

    def get_session_by_token_hash(self, token_hash: str) -> Optional[Session]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM security_sessions WHERE session_token_hash = ?;",
                (token_hash,)
            )
            r = cur.fetchone()
            return self._row_to_session(r) if r else None

    def update_session_activity(self, session_id: str, last_seen_at: datetime, idle_expires_at: datetime) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                UPDATE security_sessions
                SET last_seen_at = ?, idle_expires_at = ?
                WHERE session_id = ?;
            """, (_format_iso(last_seen_at), _format_iso(idle_expires_at), session_id))

    def revoke_session(self, session_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                UPDATE security_sessions
                SET revoked_at = ?
                WHERE session_id = ? AND revoked_at IS NULL;
            """, (_format_iso(datetime.now(timezone.utc)), session_id))

    def revoke_all_user_sessions(self, user_id: str) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("""
                UPDATE security_sessions
                SET revoked_at = ?
                WHERE user_id = ? AND revoked_at IS NULL;
            """, (_format_iso(datetime.now(timezone.utc)), user_id))
            return cur.rowcount

    def cleanup_expired_sessions(self) -> int:
        now_iso = _format_iso(datetime.now(timezone.utc))
        with self._lock, self._conn:
            cur = self._conn.execute("""
                DELETE FROM security_sessions
                WHERE revoked_at IS NOT NULL
                   OR idle_expires_at < ?
                   OR absolute_expires_at < ?;
            """, (now_iso, now_iso))
            return cur.rowcount

    # Audit Events
    def save_audit_event(self, event: AuditEvent) -> None:
        with self._lock, self._conn:
            self._conn.execute("""
                INSERT INTO security_audit_events (
                    audit_id, event_time_utc, actor_user_id, actor_username,
                    actor_role, action, resource_type, resource_id, outcome,
                    request_id, source_ip, user_agent, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                event.audit_id,
                _format_iso(event.event_time_utc),
                event.actor_user_id,
                event.actor_username,
                event.actor_role,
                event.action,
                event.resource_type,
                event.resource_id,
                event.outcome,
                event.request_id,
                event.source_ip,
                event.user_agent,
                json.dumps(event.details_json)
            ))

    def _row_to_audit_event(self, r: sqlite3.Row) -> AuditEvent:
        details = {}
        try:
            if r["details_json"]:
                details = json.loads(r["details_json"])
        except Exception:
            pass
        return AuditEvent(
            audit_id=r["audit_id"],
            event_time_utc=_parse_iso(r["event_time_utc"]) or datetime.now(timezone.utc),
            actor_user_id=r["actor_user_id"],
            actor_username=r["actor_username"],
            actor_role=r["actor_role"],
            action=r["action"],
            resource_type=r["resource_type"],
            resource_id=r["resource_id"],
            outcome=r["outcome"],
            request_id=r["request_id"],
            source_ip=r["source_ip"],
            user_agent=r["user_agent"],
            details_json=details
        )

    def query_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditEvent]:
        query = "SELECT * FROM security_audit_events WHERE 1=1"
        params: List[Any] = []

        if actor_username:
            query += " AND actor_username = ?"
            params.append(actor_username.strip().lower())
        if action:
            query += " AND action = ?"
            params.append(action.strip().upper())
        if resource_type:
            query += " AND resource_type = ?"
            params.append(resource_type.strip().lower())
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome.strip().upper())
        if start_time:
            query += " AND event_time_utc >= ?"
            params.append(_format_iso(start_time))
        if end_time:
            query += " AND event_time_utc <= ?"
            params.append(_format_iso(end_time))

        query += " ORDER BY event_time_utc DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with self._lock:
            cur = self._conn.execute(query, tuple(params))
            return [self._row_to_audit_event(r) for r in cur.fetchall()]

    def count_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        query = "SELECT COUNT(*) FROM security_audit_events WHERE 1=1"
        params: List[Any] = []

        if actor_username:
            query += " AND actor_username = ?"
            params.append(actor_username.strip().lower())
        if action:
            query += " AND action = ?"
            params.append(action.strip().upper())
        if resource_type:
            query += " AND resource_type = ?"
            params.append(resource_type.strip().lower())
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome.strip().upper())
        if start_time:
            query += " AND event_time_utc >= ?"
            params.append(_format_iso(start_time))
        if end_time:
            query += " AND event_time_utc <= ?"
            params.append(_format_iso(end_time))

        with self._lock:
            cur = self._conn.execute(query, tuple(params))
            return cur.fetchone()[0]


class PostgresSecurityRepository(BaseSecurityRepository):
    """PostgreSQL backed security repository using connection pool."""

    def __init__(self):
        import importlib
        db_mod = importlib.import_module("00_foundation.registry.database")
        self._get_connection = db_mod.get_connection
        self._init_schema()

    def _init_schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                sql = f.read()
            try:
                conn = self._get_connection()
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                conn.close()
            except Exception:
                pass

    def save_user(self, user: User) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO security_users (
                        user_id, username, display_name, password_hash, role,
                        enabled, must_change_password, created_at, updated_at,
                        last_login_at, failed_login_count, locked_until
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username=EXCLUDED.username,
                        display_name=EXCLUDED.display_name,
                        password_hash=EXCLUDED.password_hash,
                        role=EXCLUDED.role,
                        enabled=EXCLUDED.enabled,
                        must_change_password=EXCLUDED.must_change_password,
                        updated_at=EXCLUDED.updated_at,
                        last_login_at=EXCLUDED.last_login_at,
                        failed_login_count=EXCLUDED.failed_login_count,
                        locked_until=EXCLUDED.locked_until;
                """, (
                    user.user_id,
                    user.username.strip().lower(),
                    user.display_name,
                    user.password_hash,
                    user.role.value if isinstance(user.role, UserRole) else str(user.role),
                    user.enabled,
                    user.must_change_password,
                    user.created_at,
                    user.updated_at,
                    user.last_login_at,
                    user.failed_login_count,
                    user.locked_until
                ))
            conn.commit()
        finally:
            conn.close()

    def _row_to_user(self, r: tuple) -> User:
        return User(
            user_id=r[0],
            username=r[1],
            display_name=r[2],
            password_hash=r[3],
            role=UserRole(r[4]),
            enabled=bool(r[5]),
            must_change_password=bool(r[6]),
            created_at=_parse_iso(r[7]) or datetime.now(timezone.utc),
            updated_at=_parse_iso(r[8]) or datetime.now(timezone.utc),
            last_login_at=_parse_iso(r[9]),
            failed_login_count=r[10],
            locked_until=_parse_iso(r[11])
        )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM security_users WHERE user_id = %s;", (user_id,))
                r = cur.fetchone()
                return self._row_to_user(r) if r else None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[User]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM security_users WHERE username = %s;",
                    (username.strip().lower(),)
                )
                r = cur.fetchone()
                return self._row_to_user(r) if r else None
        finally:
            conn.close()

    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM security_users ORDER BY created_at ASC LIMIT %s OFFSET %s;",
                    (limit, offset)
                )
                return [self._row_to_user(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def count_users(self) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM security_users;")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def update_user(self, user: User) -> None:
        self.save_user(user)

    def count_active_admins(self) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM security_users WHERE role = 'ADMIN' AND enabled = TRUE;"
                )
                return cur.fetchone()[0]
        finally:
            conn.close()

    def save_session(self, session: Session) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO security_sessions (
                        session_id, session_token_hash, user_id, created_at,
                        last_seen_at, idle_expires_at, absolute_expires_at,
                        csrf_token_hash, revoked_at, source_ip, user_agent_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id) DO UPDATE SET
                        last_seen_at=EXCLUDED.last_seen_at,
                        idle_expires_at=EXCLUDED.idle_expires_at,
                        revoked_at=EXCLUDED.revoked_at;
                """, (
                    session.session_id,
                    session.session_token_hash,
                    session.user_id,
                    session.created_at,
                    session.last_seen_at,
                    session.idle_expires_at,
                    session.absolute_expires_at,
                    session.csrf_token_hash,
                    session.revoked_at,
                    session.source_ip,
                    session.user_agent_hash
                ))
            conn.commit()
        finally:
            conn.close()

    def _row_to_session(self, r: tuple) -> Session:
        return Session(
            session_id=r[0],
            session_token_hash=r[1],
            user_id=r[2],
            created_at=_parse_iso(r[3]) or datetime.now(timezone.utc),
            last_seen_at=_parse_iso(r[4]) or datetime.now(timezone.utc),
            idle_expires_at=_parse_iso(r[5]) or datetime.now(timezone.utc),
            absolute_expires_at=_parse_iso(r[6]) or datetime.now(timezone.utc),
            csrf_token_hash=r[7],
            revoked_at=_parse_iso(r[8]),
            source_ip=r[9],
            user_agent_hash=r[10]
        )

    def get_session_by_token_hash(self, token_hash: str) -> Optional[Session]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM security_sessions WHERE session_token_hash = %s;",
                    (token_hash,)
                )
                r = cur.fetchone()
                return self._row_to_session(r) if r else None
        finally:
            conn.close()

    def update_session_activity(self, session_id: str, last_seen_at: datetime, idle_expires_at: datetime) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE security_sessions
                    SET last_seen_at = %s, idle_expires_at = %s
                    WHERE session_id = %s;
                """, (last_seen_at, idle_expires_at, session_id))
            conn.commit()
        finally:
            conn.close()

    def revoke_session(self, session_id: str) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE security_sessions
                    SET revoked_at = %s
                    WHERE session_id = %s AND revoked_at IS NULL;
                """, (datetime.now(timezone.utc), session_id))
            conn.commit()
        finally:
            conn.close()

    def revoke_all_user_sessions(self, user_id: str) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE security_sessions
                    SET revoked_at = %s
                    WHERE user_id = %s AND revoked_at IS NULL;
                """, (datetime.now(timezone.utc), user_id))
                cnt = cur.rowcount
            conn.commit()
            return cnt
        finally:
            conn.close()

    def cleanup_expired_sessions(self) -> int:
        now = datetime.now(timezone.utc)
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM security_sessions
                    WHERE revoked_at IS NOT NULL
                       OR idle_expires_at < %s
                       OR absolute_expires_at < %s;
                """, (now, now))
                cnt = cur.rowcount
            conn.commit()
            return cnt
        finally:
            conn.close()

    def save_audit_event(self, event: AuditEvent) -> None:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO security_audit_events (
                        audit_id, event_time_utc, actor_user_id, actor_username,
                        actor_role, action, resource_type, resource_id, outcome,
                        request_id, source_ip, user_agent, details_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    event.audit_id,
                    event.event_time_utc,
                    event.actor_user_id,
                    event.actor_username,
                    event.actor_role,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.outcome,
                    event.request_id,
                    event.source_ip,
                    event.user_agent,
                    json.dumps(event.details_json)
                ))
            conn.commit()
        finally:
            conn.close()

    def _row_to_audit_event(self, r: tuple) -> AuditEvent:
        details = r[12]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        elif not isinstance(details, dict):
            details = {}
        return AuditEvent(
            audit_id=r[0],
            event_time_utc=_parse_iso(r[1]) or datetime.now(timezone.utc),
            actor_user_id=r[2],
            actor_username=r[3],
            actor_role=r[4],
            action=r[5],
            resource_type=r[6],
            resource_id=r[7],
            outcome=r[8],
            request_id=r[9],
            source_ip=r[10],
            user_agent=r[11],
            details_json=details
        )

    def query_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditEvent]:
        query = "SELECT * FROM security_audit_events WHERE 1=1"
        params: List[Any] = []

        if actor_username:
            query += " AND actor_username = %s"
            params.append(actor_username.strip().lower())
        if action:
            query += " AND action = %s"
            params.append(action.strip().upper())
        if resource_type:
            query += " AND resource_type = %s"
            params.append(resource_type.strip().lower())
        if outcome:
            query += " AND outcome = %s"
            params.append(outcome.strip().upper())
        if start_time:
            query += " AND event_time_utc >= %s"
            params.append(start_time)
        if end_time:
            query += " AND event_time_utc <= %s"
            params.append(end_time)

        query += " ORDER BY event_time_utc DESC LIMIT %s OFFSET %s;"
        params.extend([limit, offset])

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return [self._row_to_audit_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def count_audit_events(
        self,
        actor_username: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        query = "SELECT COUNT(*) FROM security_audit_events WHERE 1=1"
        params: List[Any] = []

        if actor_username:
            query += " AND actor_username = %s"
            params.append(actor_username.strip().lower())
        if action:
            query += " AND action = %s"
            params.append(action.strip().upper())
        if resource_type:
            query += " AND resource_type = %s"
            params.append(resource_type.strip().lower())
        if outcome:
            query += " AND outcome = %s"
            params.append(outcome.strip().upper())
        if start_time:
            query += " AND event_time_utc >= %s"
            params.append(start_time)
        if end_time:
            query += " AND event_time_utc <= %s"
            params.append(end_time)

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return cur.fetchone()[0]
        finally:
            conn.close()


_GLOBAL_SECURITY_REPO: BaseSecurityRepository | None = None
_REPO_LOCK = threading.Lock()


def get_security_repository() -> BaseSecurityRepository:
    global _GLOBAL_SECURITY_REPO
    if _GLOBAL_SECURITY_REPO is not None:
        return _GLOBAL_SECURITY_REPO

    with _REPO_LOCK:
        if _GLOBAL_SECURITY_REPO is not None:
            return _GLOBAL_SECURITY_REPO

        use_sqlite = os.getenv("SENTINEL_SECURITY_USE_SQLITE", "").lower() in ("true", "1", "yes")
        if not use_sqlite:
            try:
                repo = PostgresSecurityRepository()
                # Test connectivity
                repo.count_users()
                _GLOBAL_SECURITY_REPO = repo
                return _GLOBAL_SECURITY_REPO
            except Exception:
                pass

        _GLOBAL_SECURITY_REPO = SqliteSecurityRepository()
        return _GLOBAL_SECURITY_REPO


def set_security_repository(repo: BaseSecurityRepository | None) -> None:
    global _GLOBAL_SECURITY_REPO
    with _REPO_LOCK:
        _GLOBAL_SECURITY_REPO = repo

