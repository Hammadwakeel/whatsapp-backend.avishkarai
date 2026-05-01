from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
import enum

from app.core.database import Base


class SourceType(str, enum.Enum):
    ARTICLE = "article"
    PAPER = "paper"
    BOOK = "book"
    VIDEO = "video"
    PODCAST = "podcast"
    NOTE = "note"
    WEBPAGE = "webpage"
    OTHER = "other"


class WikiPageType(str, enum.Enum):
    ENTITY = "entity"
    CONCEPT = "concept"
    SOURCE = "source"
    SUMMARY = "summary"
    NOTE = "note"


class WikiSource(Base):
    __tablename__ = "wiki_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), default=SourceType.OTHER)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    original_url: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256
    tags: Mapped[str | None] = mapped_column(Text)  # JSON array
    extra_data: Mapped[str | None] = mapped_column(Text)  # JSON object
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="wiki_sources")
    wiki_pages: Mapped[list["WikiPage"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    page_type: Mapped[WikiPageType] = mapped_column(SQLEnum(WikiPageType), default=WikiPageType.NOTE)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter: Mapped[str | None] = mapped_column(Text)  # YAML frontmatter as JSON
    tags: Mapped[str | None] = mapped_column(Text)  # JSON array
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("wiki_sources.id"))
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="wiki_pages")
    source: Mapped["WikiSource | None"] = relationship(back_populates="wiki_pages")
    incoming_links: Mapped[list["WikiLink"]] = relationship(foreign_keys="WikiLink.target_page_id", back_populates="target_page")
    outgoing_links: Mapped[list["WikiLink"]] = relationship(foreign_keys="WikiLink.source_page_id", back_populates="source_page")


class WikiLink(Base):
    __tablename__ = "wiki_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    source_page_id: Mapped[str] = mapped_column(String(36), ForeignKey("wiki_pages.id"), nullable=False)
    target_page_id: Mapped[str] = mapped_column(String(36), ForeignKey("wiki_pages.id"), nullable=False)
    link_text: Mapped[str | None] = mapped_column(String(500))
    context: Mapped[str | None] = mapped_column(Text)  # Surrounding text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="wiki_links")
    source_page: Mapped["WikiPage"] = relationship(foreign_keys=[source_page_id], back_populates="outgoing_links")
    target_page: Mapped["WikiPage"] = relationship(foreign_keys=[target_page_id], back_populates="incoming_links")


class WikiLog(Base):
    __tablename__ = "wiki_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)  # ingest, query, lint, edit
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("wiki_sources.id"))
    page_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("wiki_pages.id"))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    details: Mapped[str | None] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="wiki_logs")
    source: Mapped["WikiSource | None"] = relationship()
    page: Mapped["WikiPage | None"] = relationship()
    user: Mapped["User | None"] = relationship()


# Import for relationship resolution
from app.models.tenant import Tenant
from app.models.user import User