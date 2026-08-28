import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from .models import AuditEvent, AuthenticatedPrincipal
from .repository import BaseSecurityRepository, get_security_repository

logger = logging.getLogger("sentineltrack.audit")

REDACTED_KEYS = {
    "password", "password_hash", "token", "session_token", "csrf_token",
    "secret", "authorization", "cookie", "key", "api_key"
}


def sanitize_audit_string(val: Optional[str]) -> Optional[str]:
    """Sanitizes user-controlled string to prevent log injection."""
    if val is None:
        return None
    # Strip control chars, newlines, carriage returns, null bytes
    sanitized = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f]", " ", str(val))
    return sanitized.strip()


def redact_sensitive_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts passwords, tokens, and secrets from audit payloads."""
    clean = {}
    for k, v in d.items():
        if any(r in k.lower() for r in REDACTED_KEYS):
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = redact_sensitive_dict(v)
        elif isinstance(v, str):
            clean[k] = sanitize_audit_string(v)
        else:
            clean[k] = v
    return clean


class AuditLogger:
    """Centralized, tamper-resistant security audit logging engine."""

    def __init__(self, repository: Optional[BaseSecurityRepository] = None):
        self.repo = repository or get_security_repository()

    def log_event(
        self,
        action: str,
        resource_type: str,
        outcome: str = "SUCCESS",
        principal: Optional[AuthenticatedPrincipal] = None,
        actor_username: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        fail_closed: bool = False
    ) -> AuditEvent:
        """
        Emits and persists a security audit event.
        For high-value mutations (user edit, target disable), fail_closed=True
        guarantees that an audit write failure aborts the operation safely.
        """
        now = datetime.now(timezone.utc)
        audit_id = str(uuid.uuid4())

        username = sanitize_audit_string(
            principal.username if principal else actor_username
        )
        user_id = sanitize_audit_string(principal.user_id if principal else actor_user_id)
        role = (
            principal.role.value
            if principal
            else (actor_role.value if hasattr(actor_role, "value") else actor_role)
        )

        clean_details = redact_sensitive_dict(details) if details else {}

        event = AuditEvent(
            audit_id=audit_id,
            event_time_utc=now,
            actor_user_id=user_id,
            actor_username=username,
            actor_role=role,
            action=sanitize_audit_string(action).strip().upper() if action else "UNKNOWN",
            resource_type=sanitize_audit_string(resource_type).strip().lower() if resource_type else "unknown",
            resource_id=sanitize_audit_string(resource_id),
            outcome=sanitize_audit_string(outcome).strip().upper() if outcome else "UNKNOWN",
            request_id=sanitize_audit_string(request_id),
            source_ip=sanitize_audit_string(source_ip),
            user_agent=sanitize_audit_string(user_agent),
            details_json=clean_details
        )


        try:
            self.repo.save_audit_event(event)
            logger.info(
                f"[AUDIT] action={event.action} resource={event.resource_type}:{event.resource_id} "
                f"actor={event.actor_username} outcome={event.outcome} req_id={event.request_id}"
            )
        except Exception as e:
            logger.error(f"Failed to record audit event: {e}")
            if fail_closed:
                raise RuntimeError(f"Audit log write failure for critical operation {action}: {e}")

        return event


_GLOBAL_AUDIT_LOGGER: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _GLOBAL_AUDIT_LOGGER
    if _GLOBAL_AUDIT_LOGGER is None:
        _GLOBAL_AUDIT_LOGGER = AuditLogger()
    return _GLOBAL_AUDIT_LOGGER


def set_audit_logger(logger_instance: Optional[AuditLogger]) -> None:
    global _GLOBAL_AUDIT_LOGGER
    _GLOBAL_AUDIT_LOGGER = logger_instance


