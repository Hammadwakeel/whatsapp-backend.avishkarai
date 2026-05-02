"""Journey Module Tests"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestJourneyConfig:
    """Tests for journey configuration endpoint"""

    async def test_get_config_creates_default(self, client: AsyncClient, auth_tokens):
        """Test getting config creates default if none exists"""
        response = await client.get(
            "/journey/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_enabled" in data
        assert "hotel_city" in data

    async def test_update_config(self, client: AsyncClient, auth_tokens):
        """Test updating journey configuration"""
        response = await client.post(
            "/journey/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
            json={
                "is_enabled": True,
                "hotel_city": "Lahore",
                "morning_message_hour": 8,
                "enable_weather_based": True,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hotel_city"] == "Lahore"
        assert data["enable_weather_based"] is True

    async def test_enable_journey(self, client: AsyncClient, auth_tokens):
        """Test enabling journey messaging"""
        response = await client.post(
            "/journey/config/enable",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_disable_journey(self, client: AsyncClient, auth_tokens):
        """Test disabling journey messaging"""
        response = await client.post(
            "/journey/config/disable",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestJourneyWeather:
    """Tests for weather endpoint"""

    async def test_get_weather_by_city(self, client: AsyncClient, auth_tokens):
        """Test getting weather by city name"""
        response = await client.get(
            "/journey/weather?city=Lahore",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        # May fail if API key not configured
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestJourneyGuests:
    """Tests for journey guest endpoints"""

    async def test_list_journey_guests(self, client: AsyncClient, auth_tokens):
        """Test listing guests eligible for journey messages"""
        response = await client.get(
            "/journey/guests",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "guests" in data
        assert "total" in data
        assert isinstance(data["guests"], list)

    async def test_list_journey_guests_with_status_filter(self, client: AsyncClient, auth_tokens):
        """Test listing guests filtered by status"""
        response = await client.get(
            "/journey/guests?status=Arrived,StayOver",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "guests" in data


class TestJourneyMessageLogs:
    """Tests for journey message logs"""

    async def test_get_message_logs(self, client: AsyncClient, auth_tokens):
        """Test getting journey message logs"""
        response = await client.get(
            "/journey/logs",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data

    async def test_get_message_logs_with_filter(self, client: AsyncClient, auth_tokens):
        """Test getting logs filtered by message type"""
        response = await client.get(
            "/journey/logs?message_type=morning",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200


class TestJourneyBroadcast:
    """Tests for broadcast messaging"""

    async def test_broadcast_requires_config(self, client: AsyncClient, auth_tokens):
        """Test broadcast needs proper config"""
        response = await client.post(
            "/journey/send/broadcast?message_type=morning",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        # Should work even if no guests
        assert response.status_code == 200
        data = response.json()
        assert "guests_count" in data


class TestJourneyMultiTenant:
    """Tests for multi-tenant isolation"""

    async def test_tenant_isolation(self, client: AsyncClient, auth_tokens, hotel_b_tokens):
        """Test that tenants have separate journey configs"""
        # Tenant A gets config
        config_a = await client.get(
            "/journey/config",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        # Tenant B gets config
        config_b = await client.get(
            "/journey/config",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )

        assert config_a.status_code == 200
        assert config_b.status_code == 200

        # Both should have their own configs (can have same defaults)
        assert "tenant_id" in config_a.json()
        assert "tenant_id" in config_b.json()

        # Guest lists should be separate
        guests_a = await client.get(
            "/journey/guests",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        guests_b = await client.get(
            "/journey/guests",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )

        assert guests_a.status_code == 200
        assert guests_b.status_code == 200


class TestJourneyConversation:
    """Tests for AI conversation handling"""

    async def test_conversation_requires_mobile(self, client: AsyncClient, auth_tokens):
        """Test conversation endpoint requires guest mobile"""
        response = await client.post(
            "/journey/conversation",
            params={
                "tenant_id": "test-tenant",
                "mobile": "unknown-number",
                "message": "Hello"
            }
        )
        # Should return guest_not_found for unknown number
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "guest_not_found"