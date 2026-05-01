import json
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from app.core.config import get_settings
from app.schemas.wiki import (
    IngestRequest,
    QueryRequest,
    QueryResponse,
    LintRequest,
    LintResponse,
    LintIssue,
    WikiPageResponse,
)


settings = get_settings()


class LLMService:
    """Service for LLM operations using OpenRouter"""

    def __init__(self):
        self.api_key = getattr(settings, 'openrouter_api_key', None) or getattr(settings, 'OPENROUTER_API_KEY', None)
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = getattr(settings, 'llm_model', 'anthropic/claude-3-haiku')

    async def _make_request(self, messages: list[dict], **kwargs) -> dict:
        """Make a request to OpenRouter API"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://inika-backend.local",
            "X-Title": "Inika Wiki Agent",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()

    async def generate_summary(self, content: str, source_title: str) -> str:
        """Generate a summary of source content"""
        prompt = f"""You are a wiki maintainer. Summarize the following source content in 2-3 paragraphs.

Source: {source_title}

Content:
{content[:8000] if len(content) > 8000 else content}

Provide a concise summary that captures the main points and key takeaways."""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=500)

        return result["choices"][0]["message"]["content"]

    async def extract_entities(self, content: str, source_title: str) -> list[dict]:
        """Extract entities (people, places, concepts) from content"""
        prompt = f"""You are a wiki maintainer. Extract key entities from the following content.

For each entity, provide:
- name: The entity name
- type: person, place, concept, organization, or other
- description: Brief description (1-2 sentences)

Content: {source_title}

{content[:6000] if len(content) > 6000 else content}

Return as JSON array:
[
  {{"name": "...", "type": "...", "description": "..."}}
]"""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=1000)

        content = result["choices"][0]["message"]["content"]
        # Extract JSON from response
        try:
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return []

    async def generate_page_content(
        self,
        title: str,
        page_type: str,
        source_content: str,
        existing_pages: list[str] = None
    ) -> str:
        """Generate wiki page content based on source"""
        existing_info = ""
        if existing_pages:
            existing_info = f"Existing related pages:\n" + "\n".join([f"- {p}" for p in existing_pages])

        prompt = f"""You are a wiki maintainer. Create a well-structured wiki page.

Title: {title}
Type: {page_type}

{existing_info}

Source content:
{source_content[:8000] if len(source_content) > 8000 else source_content}

Create a wiki page with:
1. YAML frontmatter (title, type, created, updated, tags)
2. Summary section (2-3 sentences)
3. Details section with main content
4. Related links section using [[Page Title]] format

Follow wiki conventions. Use markdown formatting."""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=2000)

        return result["choices"][0]["message"]["content"]

    async def answer_query(
        self,
        question: str,
        relevant_pages: list[dict],
        context: str = None
    ) -> tuple[str, list[dict]]:
        """Answer a query using relevant wiki pages"""
        context_info = ""
        if context:
            context_info = f"Additional context:\n{context}\n\n"

        pages_content = ""
        citations = []
        for i, page in enumerate(relevant_pages):
            pages_content += f"\n\n--- Page {i+1}: {page['title']} ---\n{page['content'][:2000]}"
            citations.append({
                "page_title": page['title'],
                "page_id": page.get('id', ''),
                "excerpt": page.get('summary', page['content'][:200])
            })

        prompt = f"""You are a wiki assistant. Answer the question based on the provided wiki pages.

{context_info}Question: {question}

{pages_content}

Provide a clear, helpful answer with citations. If the wiki pages don't contain enough information, say so honestly."""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=1500)

        answer = result["choices"][0]["message"]["content"]
        return answer, citations

    async def lint_wiki(
        self,
        all_pages: list[dict],
        recent_sources: list[dict]
    ) -> LintResponse:
        """Health check the wiki for issues"""
        pages_summary = "\n".join([
            f"- {p['title']} ({p['page_type']}): {p.get('summary', p['content'][:100])}"
            for p in all_pages[:50]
        ])

        prompt = f"""You are a wiki quality assurance agent. Review the wiki for issues.

Recent sources:
{chr(10).join([f"- {s['title']}: {s.get('summary', '')[:200]}" for s in recent_sources[:10]])}

Pages:
{pages_summary}

Identify:
1. **Contradictions** - claims that conflict with recent sources
2. **Orphan pages** - pages with no clear connections to others
3. **Stale content** - pages that should be updated based on newer sources
4. **Broken links** - references to non-existent pages

Return JSON:
{{
  "issues": [
    {{
      "issue_type": "contradiction|orphan|stale|broken_link",
      "description": "What the issue is",
      "affected_pages": ["page1", "page2"],
      "suggestion": "How to fix it"
    }}
  ],
  "stats": {{
    "total_pages": {len(all_pages)},
    "total_sources": {len(recent_sources)},
    "orphan_count": 0
  }}
}}"""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=2000)

        content = result["choices"][0]["message"]["content"]
        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                issues = [LintIssue(**i) for i in data.get("issues", [])]
                return LintResponse(issues=issues, stats=data.get("stats", {}))
        except (json.JSONDecodeError, Exception) as e:
            pass

        return LintResponse(issues=[], stats={"total_pages": len(all_pages), "total_sources": len(recent_sources), "orphan_count": 0})

    async def suggest_related_pages(self, page_title: str, page_content: str, existing_titles: list[str]) -> list[str]:
        """Suggest related pages for cross-referencing"""
        existing = "\n".join([f"- {t}" for t in existing_titles[:20]])

        prompt = f"""Given a wiki page, suggest 3-5 related pages that should be cross-referenced.

Page: {page_title}
Content preview: {page_content[:1000]}

Existing pages:
{existing}

Return as JSON array of page titles that should link to this page:
["Page 1", "Page 2", ...]"""

        messages = [{"role": "user", "content": prompt}]
        result = await self._make_request(messages, max_tokens=300)

        content = result["choices"][0]["message"]["content"]
        try:
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return []


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()


def slugify(title: str) -> str:
    """Convert title to URL-friendly slug"""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    slug = slug.strip('-')
    return slug[:200]