from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Set, Dict, Any


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"


class Permission(str, Enum):
    CAMERA_READ = "camera:read"
    TARGET_READ = "target:read"
    TARGET_CREATE = "target:create"
    TARGET_UPDATE = "target:update"
    TARGET_DISABLE = "target:disable"
    SIGHTING_READ = "sighting:read"
    ALERT_READ = "alert:read"
    ALERT_ACK = "alert:ack"
    ROUTE_READ = "route:read"
    SYSTEM_READ = "system:read"
    METRICS_READ = "metrics:read"
    AUDIT_READ = "audit:read"
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DISABLE = "user:disable"
    USER_RESET_PASSWORD = "user:reset_password"


@dataclass
class User:
    """Security User record."""
    user_id: str
    username: str
    display_name: str
    password_hash: str
    role: UserRole
    enabled: bool = True
    must_change_password: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.enabled



@dataclass
class Session:
    """Server-side session entity."""
    session_id: str
    session_token_hash: str
    user_id: str
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    csrf_token_hash: str
    revoked_at: Optional[datetime] = None
    source_ip: Optional[str] = None
    user_agent_hash: Optional[str] = None

    @property
    def is_active(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if now >= self.idle_expires_at:
            return False
        if now >= self.absolute_expires_at:
            return False
        return True



@dataclass
class AuthenticatedPrincipal:
    """Authenticated caller identity passed through request lifecycle."""
    user_id: str
    username: str
    display_name: str
    role: UserRole
    permissions: Set[str]
    session_id: str
    must_change_password: bool = False

    def has_permission(self, permission: str | Permission) -> bool:
        perm_val = permission.value if isinstance(permission, Permission) else str(permission)
        return perm_val in self.permissions


@dataclass
class AuditEvent:
    """Durable security audit trail event."""
    audit_id: str
    event_time_utc: datetime
    actor_user_id: Optional[str]
    actor_username: Optional[str]
    actor_role: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    outcome: str  # SUCCESS, FAILURE, DENIED
    request_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details_json: Dict[str, Any] = field(default_factory=dict)
