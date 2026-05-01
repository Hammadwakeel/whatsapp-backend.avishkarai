from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import uuid4

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    hotel_name: Mapped[str | None] = mapped_column(String(255))
    hotel_address: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    user_history_entries: Mapped[list["UserHistory"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    wiki_sources: Mapped[list["WikiSource"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    wiki_pages: Mapped[list["WikiPage"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    wiki_links: Mapped[list["WikiLink"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    wiki_logs: Mapped[list["WikiLog"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    agent_config: Mapped["AgentConfig"] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan")


# Import related models
from app.models.user import User, UserHistory, Session, RefreshToken
from app.models.wiki import WikiSource, WikiPage, WikiLink, WikiLog
from app.models.agent import AgentConfig