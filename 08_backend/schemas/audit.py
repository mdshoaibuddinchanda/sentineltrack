from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    audit_id: str
    event_time_utc: datetime
    actor_user_id: Optional[str] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    outcome: str
    request_id: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = {}


class AuditListResponse(BaseModel):
    items: List[AuditEventResponse]
    total: int

