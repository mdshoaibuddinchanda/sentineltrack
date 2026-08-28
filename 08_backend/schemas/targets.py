from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TargetPriorityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class TargetCreateRequest(BaseModel):
    registration: str = Field(..., min_length=4, max_length=20, description="Vehicle license plate registration string")
    priority: TargetPriorityEnum = Field(default=TargetPriorityEnum.NORMAL)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TargetUpdateRequest(BaseModel):
    priority: Optional[TargetPriorityEnum] = None
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TargetResponse(BaseModel):
    target_id: str
    registration: str
    normalized_registration: str
    priority: str
    enabled: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TargetListResponse(BaseModel):
    items: List[TargetResponse]
    total: int
