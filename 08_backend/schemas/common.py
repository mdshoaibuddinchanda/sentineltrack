from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of items to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Dict[str, Any] = Field(default_factory=dict)
