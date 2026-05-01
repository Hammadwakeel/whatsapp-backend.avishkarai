import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base
from app.core.config import get_settings

settings = get_settings()

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/inika_db_test"

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Import all models to register them with Base.metadata
    from app.models.tenant import Tenant
    from app.models.user import User, UserHistory, Session, RefreshToken
    from app.models.wiki import WikiSource, WikiPage, WikiLink, WikiLog

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    from app.core import get_db

    # Override the database dependency to use test database
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    # Clear dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture
async def registered_hotel(client: AsyncClient):
    """Register Hotel A"""
    hotel_data = {
        "name": "Hotel Paradise",
        "email": "hotelA@example.com",
        "password": "HotelPass123!",
        "phone": "+1234567890"
    }
    response = await client.post("/auth/register", json=hotel_data)
    if response.status_code == 201:
        return response.json()

    # If registration fails due to existing email, try login
    if response.status_code == 400 and "Email already registered" in response.json().get("detail", ""):
        login_response = await client.post("/auth/login", json={
            "email": "hotelA@example.com",
            "password": "HotelPass123!"
        })
        return login_response.json()

    raise Exception(f"Registration failed: {response.json()}")


@pytest.fixture
async def registered_hotel_b(client: AsyncClient):
    """Register Hotel B - separate tenant for isolation tests"""
    hotel_data = {
        "name": "Hotel Sunrise",
        "email": "hotelB@example.com",
        "password": "HotelPass456!",
        "phone": "+0987654321"
    }
    response = await client.post("/auth/register", json=hotel_data)
    if response.status_code == 201:
        return response.json()

    # If registration fails due to existing email, try login
    if response.status_code == 400 and "Email already registered" in response.json().get("detail", ""):
        login_response = await client.post("/auth/login", json={
            "email": "hotelB@example.com",
            "password": "HotelPass456!"
        })
        return login_response.json()

    raise Exception(f"Registration failed: {response.json()}")


@pytest.fixture
async def auth_tokens(client: AsyncClient, registered_hotel):
    """Get tokens for Hotel A"""
    return {
        "access_token": registered_hotel["access_token"],
        "refresh_token": registered_hotel["refresh_token"]
    }


@pytest.fixture
async def hotel_b_tokens(client: AsyncClient, registered_hotel_b):
    """Get tokens for Hotel B"""
    return {
        "access_token": registered_hotel_b["access_token"],
        "refresh_token": registered_hotel_b["refresh_token"]
    }