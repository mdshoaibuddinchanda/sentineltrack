from typing import List, Set
from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, max_length=64, description="Normalized username")
    password: str = Field(..., min_length=1, max_length=256, description="Account password")


class UserSummary(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str
    must_change_password: bool = False


class LoginResponse(BaseModel):
    user: UserSummary
    role: str
    permissions: List[str]
    csrf_token: str
    message: str = "Authentication successful"


class MeResponse(BaseModel):
    user: UserSummary
    role: str
    permissions: List[str]


class CsrfResponse(BaseModel):
    csrf_token: str


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=15, max_length=128)


