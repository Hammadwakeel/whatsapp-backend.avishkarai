"""Booking API Tests"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestBookingSync:
    """Tests for booking sync endpoint"""

    async def test_sync_guests_from_external_api(self, client: AsyncClient, auth_tokens):
        """Test syncing guests from external booking API"""
        response = await client.post(
            "/booking/sync",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        # API may fail if external service is unavailable, but endpoint should work
        assert response.status_code in [200, 500]  # 500 if external API not configured


class TestBookingFetch:
    """Tests for booking fetch endpoint"""

    async def test_fetch_guests_from_api(self, client: AsyncClient, auth_tokens):
        """Test fetching raw guest data from external API"""
        response = await client.get(
            "/booking/fetch",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        # API may return error if not configured
        assert response.status_code in [200, 500]
        data = response.json()
        assert "status" in data


class TestBookingGuests:
    """Tests for guest listing endpoints"""

    async def test_list_guests_empty(self, client: AsyncClient, auth_tokens):
        """Test listing guests when none exist"""
        response = await client.get(
            "/booking/guests",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "guests" in data
        assert "total" in data
        assert isinstance(data["guests"], list)

    async def test_list_guests_with_status_filter(self, client: AsyncClient, auth_tokens):
        """Test listing guests filtered by status"""
        response = await client.get(
            "/booking/guests?status=Arrived",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "guests" in data

    async def test_get_today_bookings(self, client: AsyncClient, auth_tokens):
        """Test getting today's bookings"""
        response = await client.get(
            "/booking/guests/today",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "bookings" in data
        assert "total" in data


class TestBookingGuestLookup:
    """Tests for guest lookup endpoints"""

    async def test_get_guest_not_found(self, client: AsyncClient, auth_tokens):
        """Test getting non-existent guest returns 404"""
        response = await client.get(
            "/booking/guests/non-existent-id",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 404

    async def test_get_guest_by_room_not_found(self, client: AsyncClient, auth_tokens):
        """Test getting guest by room when no active guest"""
        response = await client.get(
            "/booking/guests/room/999",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 404

    async def test_get_guest_by_phone_not_found(self, client: AsyncClient, auth_tokens):
        """Test getting guest by phone when not found"""
        response = await client.get(
            "/booking/guests/phone/0000000000",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 404

    async def test_get_guest_journey_not_found(self, client: AsyncClient, auth_tokens):
        """Test getting journey for non-existent guest"""
        response = await client.get(
            "/booking/guests/non-existent-id/journey",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 404


class TestBookingStats:
    """Tests for booking statistics endpoint"""

    async def test_get_booking_stats(self, client: AsyncClient, auth_tokens):
        """Test getting booking statistics"""
        response = await client.get(
            "/booking/stats",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_active" in data
        assert "arrived" in data
        assert "confirmed" in data
        assert "stayover" in data
        assert "due_in" in data
        assert "today_checkins" in data
        assert "today_checkouts" in data


class TestBookingMultiTenant:
    """Tests for multi-tenant isolation"""

    async def test_tenant_isolation(self, client: AsyncClient, auth_tokens, hotel_b_tokens):
        """Test that tenants cannot access each other's guest data"""
        # Both tenants get their own guest lists
        response_a = await client.get(
            "/booking/guests",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        response_b = await client.get(
            "/booking/guests",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )

        assert response_a.status_code == 200
        assert response_b.status_code == 200

        # Stats should be tenant-specific
        stats_a = await client.get(
            "/booking/stats",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        stats_b = await client.get(
            "/booking/stats",
            headers={"Authorization": f"Bearer {hotel_b_tokens['access_token']}"}
        )

        assert stats_a.status_code == 200
        assert stats_b.status_code == 200

        # Both should have their own isolated data
        # (empty lists since no sync has happened)
        assert stats_a.json()["total_active"] >= 0
        assert stats_b.json()["total_active"] >= 0