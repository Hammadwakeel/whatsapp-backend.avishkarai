import json
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.wiki import WikiSource, WikiPage, WikiLink, WikiLog, SourceType, WikiPageType
from app.schemas.wiki import (
    SourceCreate, SourceUpdate, WikiPageCreate, WikiPageUpdate,
    IngestRequest, IngestResponse, QueryRequest, QueryResponse,
    LintRequest, LintResponse, LintIssue,
    SourceResponse, WikiPageResponse, IndexResponse, LogListResponse
)
from app.services.llm_service import LLMService, compute_content_hash, slugify


class WikiService:
    """Service for wiki operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMService()
        self.wiki_root = Path(settings.wiki_path) if hasattr(settings, 'wiki_path') else Path("wiki")
        self.sources_dir = self.wiki_root / "sources"
        self.pages_dir = self.wiki_root / "pages"

    async def create_source(self, source_data: SourceCreate, content: str, user_id: Optional[str] = None) -> WikiSource:
        """Create a new source entry"""
        # Save content to file
        file_path = self._save_source_file(content, source_data.title)

        source = WikiSource(
            title=source_data.title,
            source_type=source_data.source_type,
            file_path=str(file_path),
            original_url=source_data.original_url,
            tags=json.dumps(source_data.tags) if source_data.tags else None,
            extra_data=json.dumps(source_data.extra_data) if source_data.extra_data else None,
            content_hash=compute_content_hash(content),
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    def _save_source_file(self, content: str, title: str) -> Path:
        """Save source content to file"""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(title)
        file_path = self.sources_dir / f"{slug}.md"

        # Add metadata header
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"---\ntitle: {title}\ncreated: {datetime.now(timezone.utc).isoformat()}\n---\n\n")
            f.write(content)

        return file_path

    async def get_source(self, source_id: str) -> Optional[WikiSource]:
        result = await self.db.execute(select(WikiSource).where(WikiSource.id == source_id))
        return result.scalar_one_or_none()

    async def list_sources(
        self,
        skip: int = 0,
        limit: int = 50,
        source_type: Optional[SourceType] = None,
        tags: Optional[list[str]] = None
    ) -> tuple[list[WikiSource], int]:
        """List sources with filtering"""
        query = select(WikiSource)
        count_query = select(func.count(WikiSource.id))

        if source_type:
            query = query.where(WikiSource.source_type == source_type)
            count_query = count_query.where(WikiSource.source_type == source_type)

        query = query.order_by(WikiSource.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def create_wiki_page(
        self,
        page_data: WikiPageCreate,
        user_id: Optional[str] = None,
        source: Optional[WikiSource] = None
    ) -> WikiPage:
        """Create a new wiki page"""
        slug = slugify(page_data.title)

        # Ensure unique slug
        base_slug = slug
        counter = 1
        while True:
            existing = await self.db.execute(select(WikiPage).where(WikiPage.slug == slug))
            if not existing.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Determine file path based on page type
        type_dir = self.pages_dir / page_data.page_type.value
        type_dir.mkdir(parents=True, exist_ok=True)
        file_path = type_dir / f"{slug}.md"

        # Generate frontmatter
        frontmatter = {
            "title": page_data.title,
            "type": page_data.page_type.value,
            "created": datetime.now(timezone.utc).isoformat(),
            "updated": datetime.now(timezone.utc).isoformat(),
            "tags": page_data.tags or [],
            "sources": [source.title] if source else []
        }

        # Write to file
        content = f"---\n{json.dumps(frontmatter, indent=2)}\n---\n\n{page_data.content}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        wiki_page = WikiPage(
            title=page_data.title,
            page_type=page_data.page_type,
            file_path=str(file_path),
            slug=slug,
            summary=self._extract_summary(page_data.content),
            content=page_data.content,
            frontmatter=json.dumps(frontmatter),
            tags=json.dumps(page_data.tags) if page_data.tags else None,
            is_draft=page_data.is_draft,
            source_id=source.id if source else None,
            created_by_id=user_id,
        )
        self.db.add(wiki_page)

        # Create links from content
        await self._extract_and_create_links(wiki_page)

        await self.db.commit()
        await self.db.refresh(wiki_page)
        return wiki_page

    def _extract_summary(self, content: str) -> str:
        """Extract first paragraph as summary"""
        paragraphs = content.split('\n\n')
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('#'):
                return p[:300] + ('...' if len(p) > 300 else '')
        return content[:300]

    async def _extract_and_create_links(self, page: WikiPage):
        """Extract [[wiki links]] from content and create link records"""
        wiki_link_pattern = re.compile(r'\[\[([^\]]+)\]\]')
        matches = wiki_link_pattern.findall(page.content)

        for link_text in matches:
            # Find target page by title
            result = await self.db.execute(
                select(WikiPage).where(WikiPage.title == link_text)
            )
            target = result.scalar_one_or_none()
            if target:
                link = WikiLink(
                    source_page_id=page.id,
                    target_page_id=target.id,
                    link_text=link_text,
                )
                self.db.add(link)

    async def get_wiki_page(self, page_id: str) -> Optional[WikiPage]:
        result = await self.db.execute(select(WikiPage).where(WikiPage.id == page_id))
        return result.scalar_one_or_none()

    async def get_wiki_page_by_slug(self, slug: str) -> Optional[WikiPage]:
        result = await self.db.execute(select(WikiPage).where(WikiPage.slug == slug))
        return result.scalar_one_or_none()

    async def list_wiki_pages(
        self,
        skip: int = 0,
        limit: int = 50,
        page_type: Optional[WikiPageType] = None,
        tags: Optional[list[str]] = None
    ) -> tuple[list[WikiPage], int]:
        """List wiki pages with filtering"""
        query = select(WikiPage)
        count_query = select(func.count(WikiPage.id))

        if page_type:
            query = query.where(WikiPage.page_type == page_type)
            count_query = count_query.where(WikiPage.page_type == page_type)

        query = query.order_by(WikiPage.updated_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def update_wiki_page(self, page_id: str, update_data: WikiPageUpdate) -> Optional[WikiPage]:
        """Update a wiki page"""
        page = await self.get_wiki_page(page_id)
        if not page:
            return None

        if update_data.title is not None:
            page.title = update_data.title
        if update_data.content is not None:
            page.content = update_data.content
            page.summary = self._extract_summary(update_data.content)
        if update_data.tags is not None:
            page.tags = json.dumps(update_data.tags)
        if update_data.is_draft is not None:
            page.is_draft = update_data.is_draft

        page.updated_at = datetime.now(timezone.utc)

        # Update file
        if update_data.content is not None or update_data.title is not None:
            frontmatter = json.loads(page.frontmatter) if page.frontmatter else {}
            frontmatter["updated"] = page.updated_at.isoformat()
            if update_data.tags is not None:
                frontmatter["tags"] = update_data.tags

            content = f"---\n{json.dumps(frontmatter, indent=2)}\n---\n\n{page.content}"
            with open(page.file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Re-extract links
        if update_data.content is not None:
            # Delete existing links
            await self.db.execute(
                delete(WikiLink).where(WikiLink.source_page_id == page_id)
            )
            await self._extract_and_create_links(page)

        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def delete_wiki_page(self, page_id: str) -> bool:
        """Delete a wiki page (soft delete by setting is_draft=True)"""
        page = await self.get_wiki_page(page_id)
        if not page:
            return False

        # Delete file
        file_path = Path(page.file_path)
        if file_path.exists():
            file_path.unlink()

        # Delete from database
        await self.db.execute(delete(WikiLink).where(
            or_(WikiLink.source_page_id == page_id, WikiLink.target_page_id == page_id)
        ))
        await self.db.execute(delete(WikiPage).where(WikiPage.id == page_id))

        await self.db.commit()
        return True

    async def search_wiki(self, query: str, limit: int = 10) -> list[WikiPage]:
        """Search wiki pages by title and content"""
        # Split query into keywords for better search
        keywords = query.split()
        conditions = []

        for keyword in keywords[:5]:  # Limit to 5 keywords
            pattern = f"%{keyword}%"
            conditions.append(
                or_(
                    WikiPage.title.ilike(pattern),
                    WikiPage.content.ilike(pattern),
                    WikiPage.summary.ilike(pattern)
                )
            )

        if conditions:
            # Match any keyword
            result = await self.db.execute(
                select(WikiPage)
                .where(or_(*conditions))
                .where(WikiPage.is_draft == False)
                .limit(limit)
            )
        else:
            result = await self.db.execute(
                select(WikiPage)
                .where(WikiPage.is_draft == False)
                .limit(limit)
            )

        pages = list(result.scalars().all())

        # Sort by relevance (title matches first)
        def relevance(page):
            score = 0
            query_lower = query.lower()
            if query_lower in page.title.lower():
                score += 10
            for kw in keywords:
                if kw.lower() in page.title.lower():
                    score += 2
            return -score  # Negative for ascending sort

        pages.sort(key=relevance)
        return pages

    async def log_operation(
        self,
        operation: str,
        description: str,
        user_id: Optional[str] = None,
        source_id: Optional[str] = None,
        page_id: Optional[str] = None,
        details: Optional[dict] = None
    ) -> WikiLog:
        """Log a wiki operation"""
        log_entry = WikiLog(
            operation=operation,
            description=description,
            user_id=user_id,
            source_id=source_id,
            page_id=page_id,
            details=json.dumps(details) if details else None,
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)
        return log_entry

    async def get_log_entries(self, skip: int = 0, limit: int = 50) -> tuple[list[WikiLog], int]:
        """Get log entries"""
        query = select(WikiLog).order_by(WikiLog.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        count_result = await self.db.execute(select(func.count(WikiLog.id)))

        return list(result.scalars().all()), count_result.scalar() or 0


class WikiIngestService:
    """Service for ingesting sources into the wiki"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wiki_service = WikiService(db)
        self.llm = LLMService()

    async def ingest(
        self,
        ingest_request: IngestRequest,
        user_id: Optional[str] = None
    ) -> IngestResponse:
        """Ingest a new source into the wiki"""
        created_pages = []
        updated_pages = []

        # Create source
        source = await self.wiki_service.create_source(
            WikiSourceCreate(
                title=ingest_request.title,
                source_type=ingest_request.source_type,
                original_url=ingest_request.url,
                tags=ingest_request.tags,
                extra_data=ingest_request.extra_data,
            ),
            ingest_request.content,
            user_id
        )

        # Log the ingest operation
        log_entry = await self.wiki_service.log_operation(
            operation="ingest",
            description=f"Ingested source: {ingest_request.title}",
            user_id=user_id,
            source_id=source.id,
            details={"source_type": ingest_request.source_type.value}
        )

        # Create source summary page
        source_summary = await self.wiki_service.create_wiki_page(
            WikiPageCreate(
                title=ingest_request.title,
                page_type=WikiPageType.SOURCE,
                content=ingest_request.content[:2000],
                tags=ingest_request.tags,
            ),
            user_id,
            source
        )
        created_pages.append(source_summary)

        # Generate LLM summary if requested
        if ingest_request.generate_summary:
            try:
                summary = await self.llm.generate_summary(ingest_request.content, ingest_request.title)
                source.summary = summary
                source.is_processed = True
                await self.db.commit()

                # Update source summary page with generated summary
                update_content = f"## Summary\n{summary}\n\n## WikiSource\n{ingest_request.content[:3000]}"
                await self.wiki_service.update_wiki_page(
                    source_summary.id,
                    WikiPageUpdate(content=update_content)
                )
            except Exception as e:
                # Log error but don't fail the ingest
                await self.wiki_service.log_operation(
                    operation="ingest_error",
                    description=f"LLM processing failed: {str(e)}",
                    user_id=user_id,
                    source_id=source.id,
                )

        # Extract and create entity pages if requested
        if ingest_request.create_entity_pages:
            try:
                entities = await self.llm.extract_entities(ingest_request.content, ingest_request.title)

                # Get existing page titles for reference
                existing_pages_result = await self.db.execute(select(WikiPage.title))
                existing_titles = [r[0] for r in existing_pages_result.all()]

                for entity in entities[:5]:  # Limit to 5 entities
                    entity_page = await self.wiki_service.create_wiki_page(
                        WikiPageCreate(
                            title=entity["name"],
                            page_type=WikiPageType.ENTITY,
                            content=f"## {entity['name']}\n\n{entity.get('description', '')}\n\nReferenced in: [[{ingest_request.title}]]",
                            tags=["entity", entity.get("type", "other")],
                        ),
                        user_id
                    )
                    created_pages.append(entity_page)
            except Exception as e:
                await self.wiki_service.log_operation(
                    operation="ingest_error",
                    description=f"Entity extraction failed: {str(e)}",
                    user_id=user_id,
                    source_id=source.id,
                )

        return IngestResponse(
            source=source,
            created_pages=created_pages,
            updated_pages=updated_pages,
            log_entry_id=str(log_entry.id)
        )


class WikiQueryService:
    """Service for querying the wiki"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wiki_service = WikiService(db)
        self.llm = LLMService()

    async def query(self, query_request: QueryRequest, user_id: Optional[str] = None) -> QueryResponse:
        """Query the wiki and get an answer"""
        # Search for relevant pages
        pages = await self.wiki_service.search_wiki(query_request.question, limit=query_request.max_pages)

        if not pages:
            return QueryResponse(
                answer="No relevant pages found in the wiki. Try ingesting some sources first.",
                citations=[],
                related_pages=[]
            )

        # Get page data for LLM
        page_data = [
            {"id": str(p.id), "title": p.title, "content": p.content, "summary": p.summary}
            for p in pages
        ]

        # Get answer from LLM
        try:
            answer, citations = await self.llm.answer_query(
                query_request.question,
                page_data,
                query_request.context
            )
        except Exception as e:
            answer = f"Error getting LLM response: {str(e)}. Here are the relevant pages:\n\n"
            answer += "\n\n".join([f"## {p.title}\n{p.summary or p.content[:500]}" for p in pages])
            citations = []

        # Log the query
        await self.wiki_service.log_operation(
            operation="query",
            description=f"Query: {query_request.question[:100]}",
            user_id=user_id,
            details={"page_count": len(pages)}
        )

        return QueryResponse(
            answer=answer,
            citations=citations,
            related_pages=[WikiPageResponse.model_validate(p) for p in pages[:5]]
        )


class WikiLintService:
    """Service for wiki health checks"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wiki_service = WikiService(db)
        self.llm = LLMService()

    async def lint(self, lint_request: LintRequest, user_id: Optional[str] = None) -> LintResponse:
        """Run wiki health checks"""
        # Get all pages and recent sources
        pages_result = await self.db.execute(select(WikiPage).where(WikiPage.is_draft == False))
        pages = list(pages_result.scalars().all())

        sources_result = await self.db.execute(
            select(WikiSource).order_by(WikiSource.created_at.desc()).limit(20)
        )
        sources = list(sources_result.scalars().all())

        page_data = [
            {"id": str(p.id), "title": p.title, "page_type": p.page_type.value, "content": p.content, "summary": p.summary}
            for p in pages
        ]
        source_data = [
            {"id": str(s.id), "title": s.title, "summary": s.summary, "created_at": s.created_at.isoformat()}
            for s in sources
        ]

        # Run LLM health check
        try:
            result = await self.llm.lint_wiki(page_data, source_data)
        except Exception as e:
            return LintResponse(
                issues=[LintIssue(
                    issue_type="error",
                    description=f"LLM lint failed: {str(e)}",
                    affected_pages=[],
                    suggestion="Check API configuration and try again"
                )],
                stats={"total_pages": len(pages), "total_sources": len(sources), "orphan_count": 0}
            )

        # Log the lint operation
        await self.wiki_service.log_operation(
            operation="lint",
            description=f"Lint completed: {len(result.issues)} issues found",
            user_id=user_id,
            details={"issue_count": len(result.issues)}
        )

        return result

    async def get_index(self) -> IndexResponse:
        """Get wiki index"""
        pages_result = await self.db.execute(select(WikiPage).where(WikiPage.is_draft == False))
        pages = list(pages_result.scalars().all())

        sources_result = await self.db.execute(select(WikiSource))
        sources = list(sources_result.scalars().all())

        # Count by type
        categories = {}
        for page_type in WikiPageType:
            categories[page_type.value] = sum(1 for p in pages if p.page_type == page_type)

        # Recent pages
        recent_pages = sorted(pages, key=lambda p: p.updated_at, reverse=True)[:10]

        return IndexResponse(
            total_pages=len(pages),
            total_sources=len(sources),
            categories=categories,
            recent_pages=[WikiPageResponse.model_validate(p) for p in recent_pages],
            recent_sources=[WikiSourceResponse.model_validate(s) for s in sources[:10]]
        )


# Import settings at module level
from app.core.config import get_settings
settings = get_settings()