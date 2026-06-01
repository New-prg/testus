from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None
    server_address: str = Field(min_length=1, max_length=512)
    node: int = Field(ge=1)


class UserRead(BaseModel):
    id: str
    login: str
    full_name: str | None
    role: str
    is_admin: bool
    is_active: bool
    pilot_server_address: str | None
    pilot_node: int | None
    is_demo: bool
    sync_started_at: datetime | None
    last_sync_completed_at: datetime | None
    next_sync_at: datetime | None
    last_sync_error: str | None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
