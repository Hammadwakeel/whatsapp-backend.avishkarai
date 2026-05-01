import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio


class TestSharedAPIKeys:
    """Test that API keys are shared (not per-tenant)"""

    async def test_tavily_service_initialized(self):
        """Test that TavilySearchService can be initialized with shared key"""
        from app.services.search_service import TavilySearchService

        # Should initialize without error
        service = TavilySearchService()
        # API key may be None if not configured, but service should still init
        assert hasattr(service, 'api_key')
        assert hasattr(service, 'base_url')

    async def test_llm_service_uses_shared_key(self):
        """Test that LLMService uses the shared OpenRouter key"""
        from app.services.llm_service import LLMService
        from app.core.config import get_settings

        settings = get_settings()
        service = LLMService()

        # The API key should come from shared settings
        assert service.api_key == settings.openrouter_api_key

    async def test_web_search_service_initialized(self):
        """Test that WebSearchService can be initialized"""
        from app.services.search_service import WebSearchService

        service = WebSearchService()
        assert service.tavily is not None


class TestTavilySearch:
    """Test Tavily search functionality"""

    async def test_tavily_search_returns_empty_when_no_key(self):
        """Test that Tavily returns empty results when no API key"""
        from app.services.search_service import TavilySearchService

        service = TavilySearchService()
        service.api_key = None
        results = await service.search("test query")
        assert results == []


class TestConfigSharedKeys:
    """Test shared API key configuration"""

    def test_settings_has_tavily_api_key(self):
        """Test that Settings includes TAVILY_API_KEY"""
        from app.core.config import Settings

        settings = Settings.model_fields
        assert 'tavily_api_key' in settings

    def test_settings_has_openrouter_api_key(self):
        """Test that Settings includes OPENROUTER_API_KEY"""
        from app.core.config import Settings

        settings = Settings.model_fields
        assert 'openrouter_api_key' in settings