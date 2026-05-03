"""WhatsApp API Schemas"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


class WhatsAppSessionBase(BaseModel):
    """Base schema for WhatsApp session"""
    phone_number: Optional[str] = None
    display_name: Optional[str] = None


class WhatsAppSessionCreate(WhatsAppSessionBase):
    """Schema for creating WhatsApp session"""
    pass


class WhatsAppSessionUpdate(BaseModel):
    """Schema for updating WhatsApp session"""
    openclaw_session_id: Optional[str] = None
    phone_number: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    qr_code: Optional[str] = None
    qr_expires_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    error_message: Optional[str] = None


class WhatsAppSessionResponse(BaseModel):
    """Schema for WhatsApp session response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    openclaw_session_id: Optional[str]
    phone_number: Optional[str]
    display_name: Optional[str]
    status: str
    qr_code: Optional[str]
    qr_expires_at: Optional[datetime]
    connected_at: Optional[datetime]
    last_activity: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class WhatsAppStatusResponse(BaseModel):
    """Schema for WhatsApp status response"""
    is_connected: bool
    status: str
    qrcode: Optional[str] = None
    phone_number: Optional[str]
    display_name: Optional[str]
    connected_at: Optional[datetime]
    last_activity: Optional[datetime]
    message_count: int
    local_session_id: Optional[str] = None
    pairing_code: Optional[str] = None
    evolution_detail: Optional[str] = None


class QRCodeResponse(BaseModel):
    """Schema for QR code response"""
    qr_code: str
    expires_at: datetime


class WhatsAppMessageBase(BaseModel):
    """Base schema for WhatsApp message"""
    content: str
    direction: str
    from_number: str
    to_number: Optional[str] = None


class WhatsAppMessageCreate(WhatsAppMessageBase):
    """Schema for creating WhatsApp message"""
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    agent_response: Optional[str] = None
    wiki_sources: Optional[dict] = None
    web_search_used: bool = False
    response_time_ms: Optional[int] = None


class WhatsAppMessageResponse(BaseModel):
    """Schema for WhatsApp message response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    session_id: Optional[str]
    message_id: Optional[str]
    direction: str
    from_number: str
    to_number: Optional[str]
    content: str
    agent_response: Optional[str]
    wiki_sources: Optional[dict]
    web_search_used: bool
    response_time_ms: Optional[int]
    is_delivered: bool
    created_at: datetime


class MessageListResponse(BaseModel):
    """Schema for message list response"""
    messages: list[WhatsAppMessageResponse]
    total: int
    page: int
    page_size: int


class WhatsAppSendRequest(BaseModel):
    """Manual outbound message from dashboard"""
    to: str
    message: str