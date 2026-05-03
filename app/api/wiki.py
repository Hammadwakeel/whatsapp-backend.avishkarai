"""Wiki API Routes - LLM-Powered Knowledge Base"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import Tenant
from app.schemas.wiki import (
    IngestRequest, IngestResponse,
    QueryRequest, QueryResponse,
    SourceResponse, SourceListResponse,
    WikiPageResponse, WikiPageListResponse,
    IndexResponse,
)
from app.services.wiki_service import WikiService, WikiIngestService, WikiQueryService
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/wiki", tags=["Wiki"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_source(
    ingest_request: IngestRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a new source into the wiki"""
    ingest_service = WikiIngestService(db)
    result = await ingest_service.ingest(ingest_request, current_tenant.id)
    return result


@router.post("/query", response_model=QueryResponse)
async def query_wiki(
    query_request: QueryRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Query the wiki and get an LLM-powered answer"""
    query_service = WikiQueryService(db)
    result = await query_service.query(query_request, str(current_tenant.id))
    return result


@router.get("/index", response_model=IndexResponse)
async def get_wiki_index(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get wiki overview stats"""
    wiki_service = WikiService(db)
    pages, total_pages = await wiki_service.list_wiki_pages(0, 1000)
    sources, total_sources = await wiki_service.list_sources(0, 1000)

    # Build categories
    categories = {}
    for page in pages:
        page_type = page.page_type.value if hasattr(page.page_type, 'value') else str(page.page_type)
        categories[page_type] = categories.get(page_type, 0) + 1

    return IndexResponse(
        total_pages=total_pages,
        total_sources=total_sources,
        categories=categories,
        recent_pages=pages[:10],
        recent_sources=sources[:10],
    )


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all wiki sources"""
    wiki_service = WikiService(db)
    sources, total = await wiki_service.list_sources(skip, limit)
    return SourceListResponse(
        sources=[SourceResponse.model_validate(s) for s in sources],
        total=total
    )


@router.get("/pages", response_model=WikiPageListResponse)
async def list_pages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List all wiki pages"""
    wiki_service = WikiService(db)
    pages, total = await wiki_service.list_wiki_pages(skip, limit)
    return WikiPageListResponse(
        pages=[WikiPageResponse.model_validate(p) for p in pages],
        total=total
    )


@router.get("/pages/search")
async def search_pages(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Search wiki pages"""
    wiki_service = WikiService(db)
    pages = await wiki_service.search_wiki(q, limit)
    return WikiPageListResponse(
        pages=[WikiPageResponse.model_validate(p) for p in pages],
        total=len(pages)
    )
