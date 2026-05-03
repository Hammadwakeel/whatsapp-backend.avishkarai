"""WhatsApp Tests"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestWhatsAppStatus:
    """Tests for WhatsApp status endpoint"""

    async def test_get_status_disconnected(self, client: AsyncClient, auth_tokens):
        """Test getting status when WhatsApp is not connected"""
        response = await client.get(
            "/whatsapp/status",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is False
        # Evolution reports close/disconnected or connecting when not linked yet
        assert data["status"].lower() in ("disconnected", "close", "connecting")
        assert data["phone_number"] is None


class TestWhatsAppConnect:
    """Tests for WhatsApp connect endpoint"""

    async def test_connect_returns_session(self, client: AsyncClient, auth_tokens):
        """Test that connect creates a session"""
        response = await client.post(
            "/whatsapp/connect",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "local_session_id" in data
        assert "status" in data
        assert data["status"] in ["connecting", "connected", "qr_available", "waiting", "error"]


class TestWhatsAppDisconnect:
    """Tests for WhatsApp disconnect endpoint"""

    async def test_disconnect_works(self, client: AsyncClient, auth_tokens):
        """Test disconnecting WhatsApp"""
        # First connect
        await client.post(
            "/whatsapp/connect",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )

        # Then disconnect
        response = await client.post(
            "/whatsapp/disconnect",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestWhatsAppSession:
    """Tests for WhatsApp session endpoint"""

    async def test_get_session_creates_new(self, client: AsyncClient, auth_tokens):
        """Test that GET /whatsapp/session creates a new session if none exists"""
        response = await client.get(
            "/whatsapp/session",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["tenant_id"] is not None


class TestWhatsAppMessages:
    """Tests for WhatsApp messages endpoint"""

    async def test_get_messages_empty(self, client: AsyncClient, auth_tokens):
        """Test getting messages when none exist"""
        response = await client.get(
            "/whatsapp/messages",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_get_messages_pagination(self, client: AsyncClient, auth_tokens):
        """Test message pagination"""
        response = await client.get(
            "/whatsapp/messages?page=1&page_size=10",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestWhatsAppMultiTenant:
    """Tests for multi-tenant isolation of WhatsApp"""

    async def test_tenant_isolation(
        self, client: AsyncClient, auth_tokens, hotel_b_tokens
    ):
        """Test that tenants cannot access each other's WhatsApp sessions"""
        # Hotel A connects
        session_a = await client.post(
            "/whatsapp/connect",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert session_a.status_code == 200
        hotel_a_session_id = session_a.json()["local_session_id"]

        # Hotel B connects
        session_b = await client.post(
            "/whatsapp/connect",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )
        assert session_b.status_code == 200
        hotel_b_session_id = session_b.json()["local_session_id"]

        # Verify different sessions
        assert hotel_a_session_id != hotel_b_session_id

        # Hotel A gets their session
        get_a = await client.get(
            "/whatsapp/session",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert get_a.json()["id"] == hotel_a_session_id

        # Hotel B gets their session
        get_b = await client.get(
            "/whatsapp/session",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )
        assert get_b.json()["id"] == hotel_b_session_id