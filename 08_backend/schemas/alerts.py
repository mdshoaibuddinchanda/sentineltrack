from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict



class AlertResponse(BaseModel):
    alert_id: str
    watchlist_id: str
    sighting_id: str
    camera_id: str
    stream_epoch: int
    track_id: int
    registration: str
    match_score: float
    match_class: str
    severity: str
    created_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    explanation: List[str] = Field(default_factory=list)


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    unacknowledged_count: int


class AlertAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledged_by: str = Field(default="operator", description="Operator identity acknowledging the alert")



class AlertAckResponse(BaseModel):
    success: bool
    alert_id: str
    acknowledged: bool
    acknowledged_by: str
    acknowledged_at: datetime
