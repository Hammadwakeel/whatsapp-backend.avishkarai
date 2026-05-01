import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestAuth:
    async def test_register(self, client: AsyncClient):
        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "StrongPass123!",
                "full_name": "New User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user):
        response = await client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "username": "differentuser",
                "password": "StrongPass123!"
            }
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    async def test_login_success(self, client: AsyncClient, registered_user):
        response = await client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        response = await client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword!"
            }
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_get_me_authenticated(self, client: AsyncClient, auth_tokens):
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        response = await client.get("/auth/me")
        assert response.status_code == 403

    async def test_refresh_token(self, client: AsyncClient, auth_tokens):
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": auth_tokens["refresh_token"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )
        assert response.status_code == 401


class TestUsers:
    async def test_update_profile(self, client: AsyncClient, auth_tokens):
        response = await client.patch(
            "/users/me",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"

    async def test_change_password(self, client: AsyncClient, auth_tokens):
        response = await client.post(
            "/users/me/password",
            json={
                "current_password": "TestPass123!",
                "new_password": "NewStrongPass456!"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 204

        # Verify old password doesn't work
        login_response = await client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPass123!"
            }
        )
        assert login_response.status_code == 401

    async def test_change_password_wrong_current(self, client: AsyncClient, auth_tokens):
        response = await client.post(
            "/users/me/password",
            json={
                "current_password": "WrongPassword!",
                "new_password": "NewStrongPass456!"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 400

    async def test_get_my_history(self, client: AsyncClient, auth_tokens):
        response = await client.get(
            "/users/me/history",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert "total" in data

    async def test_get_my_sessions(self, client: AsyncClient, auth_tokens):
        response = await client.get(
            "/users/me/sessions",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data


class TestHealth:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_root(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Inika Backend API"
        assert "version" in data