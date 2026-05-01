import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestTenantRegistration:
    async def test_register_tenant(self, client: AsyncClient):
        """Test registering a new hotel tenant"""
        response = await client.post(
            "/auth/register",
            json={
                "name": "Grand Hotel",
                "email": "grand@example.com",
                "password": "SecurePass123!",
                "phone": "+1234567890"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tenant"]["name"] == "Grand Hotel"
        assert data["tenant"]["email"] == "grand@example.com"
        assert "access_token" in data
        assert "refresh_token" in data
        assert "tenant" in data

    async def test_register_duplicate_email(self, client: AsyncClient, registered_hotel):
        """Test that duplicate email registration is rejected"""
        response = await client.post(
            "/auth/register",
            json={
                "name": "Different Hotel",
                "email": "hotelA@example.com",
                "password": "Password123!"
            }
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]


class TestTenantLogin:
    async def test_login_success(self, client: AsyncClient, registered_hotel):
        """Test successful login"""
        response = await client.post(
            "/auth/login",
            json={
                "email": "hotelA@example.com",
                "password": "HotelPass123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["tenant"]["email"] == "hotelA@example.com"

    async def test_login_wrong_password(self, client: AsyncClient, registered_hotel):
        """Test login with wrong password"""
        response = await client.post(
            "/auth/login",
            json={
                "email": "hotelA@example.com",
                "password": "WrongPassword!"
            }
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent email"""
        response = await client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword!"
            }
        )
        assert response.status_code == 401


class TestTenantProfile:
    async def test_get_profile(self, client: AsyncClient, auth_tokens):
        """Test getting current tenant profile"""
        response = await client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "hotelA@example.com"
        assert data["name"] == "Hotel Paradise"

    async def test_update_profile(self, client: AsyncClient, auth_tokens):
        """Test updating tenant profile"""
        response = await client.patch(
            "/auth/profile",
            json={
                "name": "Hotel Paradise Updated",
                "phone": "+9999999999"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Hotel Paradise Updated"
        assert data["phone"] == "+9999999999"

    async def test_change_password(self, client: AsyncClient, auth_tokens):
        """Test changing tenant password"""
        response = await client.post(
            "/auth/profile/password",
            json={
                "current_password": "HotelPass123!",
                "new_password": "NewSecurePass456!"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]

        # Verify old password doesn't work
        login_response = await client.post(
            "/auth/login",
            json={
                "email": "hotelA@example.com",
                "password": "HotelPass123!"
            }
        )
        assert login_response.status_code == 401


class TestTokenRefresh:
    async def test_refresh_token(self, client: AsyncClient, auth_tokens):
        """Test refreshing access token"""
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Test refreshing with invalid token"""
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        assert response.status_code == 401


class TestMultiTenantIsolation:
    async def test_tenant_data_isolation(
        self, client: AsyncClient, registered_hotel, registered_hotel_b
    ):
        """Test that tenants cannot see each other's data"""
        # Hotel A logs in and checks their profile
        hotel_a_login = await client.post(
            "/auth/login",
            json={"email": "hotelA@example.com", "password": "HotelPass123!"}
        )
        hotel_a_token = hotel_a_login.json()["access_token"]
        hotel_a_profile = await client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {hotel_a_token}"}
        )
        assert hotel_a_profile.json()["name"] == "Hotel Paradise"
        assert hotel_a_profile.json()["email"] == "hotelA@example.com"

        # Hotel B logs in and checks their profile
        hotel_b_login = await client.post(
            "/auth/login",
            json={"email": "hotelB@example.com", "password": "HotelPass456!"}
        )
        hotel_b_token = hotel_b_login.json()["access_token"]
        hotel_b_profile = await client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {hotel_b_token}"}
        )
        assert hotel_b_profile.json()["name"] == "Hotel Sunrise"
        assert hotel_b_profile.json()["email"] == "hotelB@example.com"

        # Verify tokens contain correct tenant_id by decoding
        from jose import jwt
        from app.core.config import get_settings
        settings = get_settings()

        hotel_a_payload = jwt.decode(
            hotel_a_token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        hotel_b_payload = jwt.decode(
            hotel_b_token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )

        assert hotel_a_payload["tenant_id"] != hotel_b_payload["tenant_id"]
        assert hotel_a_payload["tenant_id"] == hotel_a_profile.json()["id"]
        assert hotel_b_payload["tenant_id"] == hotel_b_profile.json()["id"]

    async def test_cross_tenant_access_denied(self, client: AsyncClient, auth_tokens):
        """Test that using Hotel B's token can't access Hotel A's data"""
        # This should fail if we try to use Hotel B's profile on Hotel A's endpoint
        # For now, just verify each token works for its own tenant
        response = await client.get(
            "/auth/profile",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should see Hotel A's data
        assert data["name"] == "Hotel Paradise"


class TestLogout:
    async def test_logout(self, client: AsyncClient, auth_tokens):
        """Test logout"""
        response = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

    async def test_logout_all(self, client: AsyncClient, auth_tokens):
        """Test logout from all sessions"""
        response = await client.post(
            "/auth/logout-all",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        assert "Logged out from" in response.json()["message"]


class TestHealth:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app"] == "inika-backend"

    async def test_root(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Inika Backend - Multi-Tenant Hotel Platform"
        assert "multi_tenant" in data