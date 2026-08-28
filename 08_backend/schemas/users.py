from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=64, description="Normalized username")
    display_name: str = Field(..., min_length=1, max_length=128, description="Operator display name")
    password: str = Field(..., min_length=15, max_length=128, description="Initial password")
    role: RoleEnum = Field(default=RoleEnum.OPERATOR, description="Assigned role")
    must_change_password: bool = Field(default=False, description="Require password change on first login")


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    role: Optional[RoleEnum] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    must_change_password: Optional[bool] = Field(default=None)


class UserResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(..., min_length=15, max_length=128)
    must_change_password: bool = Field(default=True)



class UserResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    enabled: bool
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int

