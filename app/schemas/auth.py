from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from app.models.user import UserRole


# Auth schemas
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


# History schemas
class HistoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    entity_type: str
    entity_id: Optional[str]
    changes: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime


class HistoryListResponse(BaseModel):
    history: list[HistoryEntryResponse]
    total: int


# Session schemas
class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_active: bool
    created_at: datetime
    expires_at: datetime
    last_activity: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# Token payload
class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str
    jti: Optional[str] = None