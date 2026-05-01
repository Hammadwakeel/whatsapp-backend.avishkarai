"""Agent Service - Manages agent configuration per tenant"""

from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AgentConfig, Tenant
from app.schemas.agent import (
    AgentConfigCreate, AgentConfigUpdate, AgentConfigResponse,
    AgentTestRequest, AgentTestResponse,
)
from app.services.llm_service import LLMService
from app.services.search_service import web_search


class AgentService:
    """Service for managing agent configuration and testing"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_config(self, tenant_id: str) -> AgentConfig:
        """Get existing config or create new one for tenant"""
        result = await self.db.execute(
            select(AgentConfig).where(AgentConfig.tenant_id == tenant_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            config = AgentConfig(
                tenant_id=tenant_id,
                system_prompt=None,
                personality_prompt=None,
                is_configured=False,
            )
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)

        return config

    async def get_config(self, tenant_id: str) -> Optional[AgentConfig]:
        """Get agent config for tenant"""
        result = await self.db.execute(
            select(AgentConfig).where(AgentConfig.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_config(
        self,
        tenant_id: str,
        update_data: AgentConfigUpdate
    ) -> AgentConfig:
        """Update agent config for tenant"""
        config = await self.get_or_create_config(tenant_id)

        if update_data.system_prompt is not None:
            config.system_prompt = update_data.system_prompt
        if update_data.personality_prompt is not None:
            config.personality_prompt = update_data.personality_prompt

        # Update configured status
        config.is_configured = bool(config.system_prompt or config.personality_prompt)
        config.updated_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)

        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def delete_config(self, tenant_id: str) -> bool:
        """Delete agent config for tenant"""
        config = await self.get_config(tenant_id)
        if not config:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def test_agent(
        self,
        tenant_id: str,
        request: AgentTestRequest
    ) -> AgentTestResponse:
        """Test the agent with a question"""
        config = await self.get_config(tenant_id)
        agent_config_used = config is not None and config.is_configured

        # Build prompt with agent config
        system_prompt = ""
        if config and config.system_prompt:
            system_prompt = config.system_prompt + "\n\n"

        if config and config.personality_prompt:
            system_prompt += f"Personality: {config.personality_prompt}\n\n"

        # Search wiki for relevant content
        from app.services.wiki_service import WikiService
        wiki_service = WikiService(self.db)
        pages = await wiki_service.search_wiki(request.question, limit=5)

        wiki_context = len(pages) > 0
        web_search_used = False

        if pages:
            # Use wiki content
            page_data = [
                {"id": str(p.id), "title": p.title, "content": p.content, "summary": p.summary}
                for p in pages
            ]

            llm = LLMService()
            answer, citations = await llm.answer_query(
                request.question,
                page_data,
                request.context
            )
            sources = [c["page_title"] for c in citations]
        else:
            # Fallback to web search
            if config and config.system_prompt:
                answer = f"I don't have information about that in my knowledge base. "
                answer += f"Let me search the web for you.\n\n"
            else:
                answer = "I don't have information about that in my knowledge base. "
                answer += "Please add content to your knowledge base first."

            web_results = await web_search.search(request.question, max_results=3)
            if web_results:
                web_search_used = True
                answer += "\n\n**Web Search Results:**\n"
                for r in web_results:
                    answer += f"- [{r['title']}]({r['url']}): {r['content'][:100]}...\n"
                sources = [r['title'] for r in web_results]
            else:
                sources = []

        return AgentTestResponse(
            answer=answer,
            sources=sources,
            agent_config_used=agent_config_used,
            wiki_context=wiki_context,
            web_search_used=web_search_used,
        )

    async def get_agent_status(self, tenant_id: str) -> dict:
        """Get agent configuration status"""
        config = await self.get_config(tenant_id)

        return {
            "is_configured": config.is_configured if config else False,
            "has_system_prompt": bool(config.system_prompt) if config else False,
            "has_personality_prompt": bool(config.personality_prompt) if config else False,
            "config_id": config.id if config else None,
        }