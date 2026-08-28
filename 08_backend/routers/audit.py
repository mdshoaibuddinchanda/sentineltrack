import importlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query

try:
    from ..schemas.audit import AuditEventResponse, AuditListResponse
except (ImportError, ValueError):
    sch_m = importlib.import_module("08_backend.schemas.audit")
    AuditEventResponse, AuditListResponse = sch_m.AuditEventResponse, sch_m.AuditListResponse

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
Permission = _sec_m.Permission
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
get_security_repository = _sec_m.get_security_repository
require_permission = importlib.import_module("10_security.dependencies").require_permission

router = APIRouter(prefix="/api/v1/audit", tags=["Security Audit Trail"])


@router.get("", response_model=AuditListResponse)
async def list_audit_events(
    actor_username: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    repo = Depends(get_security_repository)
):
    """
    Queries immutable security audit trail events (ADMIN, SUPERVISOR, AUDITOR).
    Filters by actor, action type, resource, outcome, and time range.
    """
    events = repo.query_audit_events(
        actor_username=actor_username,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )
    total = repo.count_audit_events(
        actor_username=actor_username,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        start_time=start_time,
        end_time=end_time
    )

    items = [
        AuditEventResponse(
            audit_id=e.audit_id,
            event_time_utc=e.event_time_utc,
            actor_user_id=e.actor_user_id,
            actor_username=e.actor_username,
            actor_role=e.actor_role,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            outcome=e.outcome,
            request_id=e.request_id,
            source_ip=e.source_ip,
            user_agent=e.user_agent,
            details=e.details_json
        )
        for e in events
    ]

    return AuditListResponse(items=items, total=total)

