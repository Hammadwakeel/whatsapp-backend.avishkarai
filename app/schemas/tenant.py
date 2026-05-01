from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional


class TenantCreate(BaseModel):
    name: str = Field(..., max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    hotel_name: Optional[str] = Field(None, max_length=255)
    hotel_address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)


class TenantLogin(BaseModel):
    email: EmailStr
    password: str


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    hotel_name: Optional[str] = None
    hotel_address: Optional[str] = None
    phone: Optional[str] = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    hotel_name: Optional[str]
    hotel_address: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant: TenantResponse