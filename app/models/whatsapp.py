"""WhatsApp Session Models"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4
from enum import Enum as PyEnum

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class SessionStatus(str, PyEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


if TYPE_CHECKING:
    from app.models.tenant import Tenant


def _utc_now():
    return datetime.now(timezone.utc)


class WhatsAppSession(Base):
    """WhatsApp session per tenant - manages OpenClaw connection"""
    __tablename__ = "whatsapp_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id"),
        unique=True,
        nullable=False
    )
    openclaw_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=SessionStatus.DISCONNECTED.value)
    qr_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qr_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Per-tenant session name for WhatsApp gateway
    gateway_session_name: Mapped[Optional[str]] = mapped_column(String(255), name="evolution_instance_name", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="whatsapp_session")
    messages: Mapped[list["WhatsAppMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class WhatsAppMessage(Base):
    """WhatsApp messages for conversation history"""
    __tablename__ = "whatsapp_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("whatsapp_sessions.id"),
        nullable=True,
        index=True
    )
    message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # inbound / outbound
    from_number: Mapped[str] = mapped_column(String(50), nullable=False)
    to_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wiki_sources: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    web_search_used: Mapped[bool] = mapped_column(Boolean, default=False)
    response_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, index=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="whatsapp_messages")
    session: Mapped[Optional["WhatsAppSession"]] = relationship(back_populates="messages")