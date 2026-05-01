from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Any
from app.models.wiki import SourceType, WikiPageType
import json


def parse_tags(v: Any) -> Optional[list[str]]:
    """Parse tags from JSON string or list"""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return None


# Source schemas
class SourceCreate(BaseModel):
    title: str = Field(..., max_length=500)
    source_type: SourceType = SourceType.OTHER
    original_url: Optional[str] = None
    tags: Optional[list[str]] = None
    extra_data: Optional[dict] = None


class SourceUpdate(BaseModel):
    title: Optional[str] = None
    source_type: Optional[SourceType] = None
    tags: Optional[list[str]] = None
    extra_data: Optional[dict] = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_type: SourceType
    file_path: str
    original_url: Optional[str]
    summary: Optional[str]
    tags: Optional[list[str]] = None
    is_processed: bool
    created_at: datetime
    updated_at: datetime

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        return parse_tags(v)


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]
    total: int


# Wiki page schemas
class WikiPageCreate(BaseModel):
    title: str = Field(..., max_length=500)
    page_type: WikiPageType = WikiPageType.NOTE
    content: str
    tags: Optional[list[str]] = None
    source_id: Optional[str] = None
    is_draft: bool = False


class WikiPageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    is_draft: Optional[bool] = None


class WikiPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    page_type: WikiPageType
    file_path: str
    slug: str
    summary: Optional[str]
    content: str
    tags: Optional[list[str]] = None
    is_draft: bool
    created_at: datetime
    updated_at: datetime

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v):
        return parse_tags(v)


class WikiPageListResponse(BaseModel):
    pages: list[WikiPageResponse]
    total: int


# Ingest schemas
class IngestRequest(BaseModel):
    source_type: SourceType = SourceType.ARTICLE
    title: str = Field(..., max_length=500)
    content: str
    url: Optional[str] = None
    tags: Optional[list[str]] = None
    extra_data: Optional[dict] = None  # Renamed from metadata
    # LLM processing options
    generate_summary: bool = True
    create_entity_pages: bool = True
    update_related_pages: bool = True


class IngestResponse(BaseModel):
    source: SourceResponse
    created_pages: list[WikiPageResponse]
    updated_pages: list[WikiPageResponse]
    log_entry_id: str


# Query schemas
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: Optional[str] = None  # Additional context for the query
    max_pages: int = Field(default=10, ge=1, le=50)


class QueryResponse(BaseModel):
    answer: str
    citations: list[dict]  # [{page_title, page_id, excerpt}]
    related_pages: list[WikiPageResponse]


# Lint schemas
class LintRequest(BaseModel):
    check_contradictions: bool = True
    check_orphans: bool = True
    check_stale: bool = True
    check_links: bool = True


class LintIssue(BaseModel):
    issue_type: str  # contradiction, orphan, stale, broken_link
    description: str
    affected_pages: list[str]
    suggestion: Optional[str] = None


class LintResponse(BaseModel):
    issues: list[LintIssue]
    stats: dict  # {total_pages, total_sources, total_links, orphan_count}


# Index schemas
class IndexResponse(BaseModel):
    total_pages: int
    total_sources: int
    categories: dict  # {entity: count, concept: count, ...}
    recent_pages: list[WikiPageResponse]
    recent_sources: list[SourceResponse]


# Log schemas
class LogEntry(BaseModel):
    id: str
    operation: str
    description: str
    created_at: datetime


class LogListResponse(BaseModel):
    entries: list[LogEntry]
    total: int