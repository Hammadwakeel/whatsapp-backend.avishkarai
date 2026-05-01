from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import Tenant
from app.schemas.wiki import (
    IngestRequest, IngestResponse,
    QueryRequest, QueryResponse,
    LintRequest, LintResponse,
    SourceResponse, SourceListResponse,
    WikiPageResponse, WikiPageListResponse,
    IndexResponse, LogListResponse,
    WikiPageCreate, WikiPageUpdate,
)
from app.services.wiki_service import WikiService, WikiIngestService, WikiQueryService, WikiLintService
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/wiki", tags=["Wiki"])


# ============ Ingest ============

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_source(
    ingest_request: IngestRequest,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a new source into the wiki"""
    ingest_service = WikiIngestService(db)

    result = await ingest_service.ingest(ingest_request, current_tenant.id)
    return result


@router.post("/ingest/async", status_code=status.HTTP_202_ACCEPTED)
async def ingest_source_async(
    ingest_request: IngestRequest,
    background_tasks: BackgroundTasks,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Queue source for async ingestion"""
    # TODO: Implement with task queue (Celery/ARQ)
    return {"message": "Ingestion queued", "status": "pending"}


# ============ Query ============

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


# ============ Lint ============

@router.post("/lint", response_model=LintResponse)
async def lint_wiki(
    lint_request: LintRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Run wiki health checks"""
    lint_service = WikiLintService(db)
    result = await lint_service.lint(lint_request, str(current_tenant.id))
    return result


# ============ Index ============

@router.get("/index", response_model=IndexResponse)
async def get_wiki_index(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get wiki index overview"""
    lint_service = WikiLintService(db)
    result = await lint_service.get_index()
    return result


# ============ Sources ============

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


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get source details"""
    wiki_service = WikiService(db)
    source = await wiki_service.get_source(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )
    return source


# ============ Pages ============

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


@router.post("/pages", response_model=WikiPageResponse, status_code=status.HTTP_201_CREATED)
async def create_page(
    page_data: WikiPageCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new wiki page"""
    wiki_service = WikiService(db)
    page = await wiki_service.create_wiki_page(page_data, str(current_tenant.id))
    return page


@router.get("/pages/{page_id}", response_model=WikiPageResponse)
async def get_page(
    page_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get wiki page by ID"""
    wiki_service = WikiService(db)
    page = await wiki_service.get_wiki_page(page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    return page


@router.get("/pages/slug/{slug}", response_model=WikiPageResponse)
async def get_page_by_slug(
    slug: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get wiki page by slug"""
    wiki_service = WikiService(db)
    page = await wiki_service.get_wiki_page_by_slug(slug)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    return page


@router.patch("/pages/{page_id}", response_model=WikiPageResponse)
async def update_page(
    page_id: str,
    update_data: WikiPageUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update a wiki page"""
    wiki_service = WikiService(db)
    page = await wiki_service.update_wiki_page(page_id, update_data)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )
    return page


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Delete a wiki page"""
    wiki_service = WikiService(db)
    success = await wiki_service.delete_wiki_page(page_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Page not found"
        )


# ============ Log ============

@router.get("/log", response_model=LogListResponse)
async def get_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get wiki operation log"""
    wiki_service = WikiService(db)
    entries, total = await wiki_service.get_log_entries(skip, limit)
    return LogListResponse(
        entries=[{
            "id": str(e.id),
            "operation": e.operation,
            "description": e.description,
            "created_at": e.created_at
        } for e in entries],
        total=total
    )