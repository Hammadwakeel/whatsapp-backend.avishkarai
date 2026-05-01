"""Agent Configuration Tests"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestAgentConfig:
    """Tests for agent configuration endpoints"""

    async def test_get_config_creates_new(self, client: AsyncClient, auth_tokens):
        """Test that GET /agent/config creates a new config if none exists"""
        response = await client.get(
            "/agent/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "tenant_id" in data
        assert data["is_configured"] is False
        assert data["system_prompt"] is None
        assert data["personality_prompt"] is None

    async def test_create_config(self, client: AsyncClient, auth_tokens):
        """Test creating agent configuration"""
        response = await client.post(
            "/agent/config",
            json={
                "system_prompt": "You are a helpful hotel assistant.",
                "personality_prompt": "Be friendly and professional."
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["system_prompt"] == "You are a helpful hotel assistant."
        assert data["personality_prompt"] == "Be friendly and professional."
        assert data["is_configured"] is True

    async def test_update_config(self, client: AsyncClient, auth_tokens):
        """Test partial update of agent configuration"""
        # First create a config
        await client.post(
            "/agent/config",
            json={
                "system_prompt": "Initial prompt",
                "personality_prompt": "Initial personality"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        # Update only system_prompt
        response = await client.patch(
            "/agent/config",
            json={"system_prompt": "Updated prompt"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["system_prompt"] == "Updated prompt"
        assert data["personality_prompt"] == "Initial personality"

    async def test_delete_config(self, client: AsyncClient, auth_tokens):
        """Test deleting agent configuration"""
        # Create a config first
        await client.post(
            "/agent/config",
            json={"system_prompt": "To be deleted"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        # Delete it
        response = await client.delete(
            "/agent/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            "/agent/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        data = get_response.json()
        assert data["is_configured"] is False

    async def test_delete_nonexistent_config(self, client: AsyncClient, auth_tokens):
        """Test deleting non-existent config returns 404"""
        response = await client.delete(
            "/agent/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 404


class TestAgentStatus:
    """Tests for agent status endpoint"""

    async def test_get_status_unconfigured(self, client: AsyncClient, auth_tokens):
        """Test getting status when agent is not configured"""
        # First create a config so config_id exists
        await client.post(
            "/agent/config",
            json={},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        response = await client.get(
            "/agent/status",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_configured"] is False
        assert data["has_system_prompt"] is False
        assert data["has_personality_prompt"] is False
        assert data["config_id"] is not None

    async def test_get_status_configured(self, client: AsyncClient, auth_tokens):
        """Test getting status when agent is configured"""
        # Create config
        await client.post(
            "/agent/config",
            json={
                "system_prompt": "Hotel assistant",
                "personality_prompt": "Friendly"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        response = await client.get(
            "/agent/status",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_configured"] is True
        assert data["has_system_prompt"] is True
        assert data["has_personality_prompt"] is True


class TestAgentTest:
    """Tests for agent test endpoint"""

    async def test_test_agent_without_content(self, client: AsyncClient, auth_tokens):
        """Test agent test returns appropriate message when no wiki content"""
        response = await client.post(
            "/agent/test",
            json={"question": "What are your check-in times?"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["agent_config_used"] is False
        assert data["wiki_context"] is False
        # Should fall back to web search or provide appropriate message

    async def test_test_agent_with_config(self, client: AsyncClient, auth_tokens):
        """Test agent test uses configuration when present"""
        # Create config
        await client.post(
            "/agent/config",
            json={"system_prompt": "You are a luxury hotel concierge."},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        response = await client.post(
            "/agent/test",
            json={"question": "What amenities do you offer?"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["agent_config_used"] is True


class TestAgentMultiTenant:
    """Tests for multi-tenant isolation of agent config"""

    async def test_tenant_isolation(
        self, client: AsyncClient, registered_hotel, registered_hotel_b,
        auth_tokens, hotel_b_tokens
    ):
        """Test that tenants cannot access each other's agent configs"""
        # Hotel A creates config
        response_a = await client.post(
            "/agent/config",
            json={"system_prompt": "Hotel A specific prompt"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response_a.status_code == 201
        assert response_a.json()["system_prompt"] == "Hotel A specific prompt"

        # Hotel B creates config
        response_b = await client.post(
            "/agent/config",
            json={"system_prompt": "Hotel B specific prompt"},
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )
        assert response_b.status_code == 201
        assert response_b.json()["system_prompt"] == "Hotel B specific prompt"

        # Hotel A gets their config
        get_a = await client.get(
            "/agent/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert get_a.json()["system_prompt"] == "Hotel A specific prompt"

        # Hotel B gets their config
        get_b = await client.get(
            "/agent/config",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )
        assert get_b.json()["system_prompt"] == "Hotel B specific prompt"

        # Verify they are different configs
        assert get_a.json()["id"] != get_b.json()["id"]