"""Tavily Search Service - Web search fallback for RAG"""

import json
from typing import Optional, List
from app.core.config import get_settings

settings = get_settings()


class TavilySearchService:
    """Service for web search using Tavily API"""

    def __init__(self):
        self.api_key = getattr(settings, 'tavily_api_key', None) or getattr(settings, 'TAVILY_API_KEY', None)
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str, max_results: int = 5) -> List[dict]:
        """Search the web for relevant information"""
        import httpx

        if not self.api_key:
            return []

        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
            "include_raw_content": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", "")[:500],
                        "score": item.get("score", 0),
                    })

                return results
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []

    async def get_answer(self, query: str, search_results: List[dict]) -> str:
        """Generate an answer from search results"""
        if not search_results:
            return "No relevant information found."

        context = "\n\n".join([
            f"Source: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
            for r in search_results[:3]
        ])

        prompt = f"""Based on the following web search results, answer the question concisely.

Question: {query}

Search Results:
{context}

Provide a direct answer. If the information is insufficient, say so."""

        messages = [{"role": "user", "content": prompt}]

        from app.services.llm_service import LLMService
        llm = LLMService()
        result = await llm._make_request(messages, max_tokens=500)
        return result["choices"][0]["message"]["content"]


class WebSearchService:
    """Web search service - falls back to Tavily"""

    def __init__(self):
        self.tavily = TavilySearchService()

    async def search(self, query: str, max_results: int = 5) -> List[dict]:
        """Search the web for relevant information"""
        return await self.tavily.search(query, max_results)

    async def search_and_answer(self, query: str) -> tuple[str, List[dict]]:
        """Search and generate an answer"""
        results = await self.search(query, max_results=5)

        if not results:
            return "I couldn't find any relevant information on the web.", []

        answer = await self.tavily.get_answer(query, results)
        return answer, results


# Global instance
web_search = WebSearchService()