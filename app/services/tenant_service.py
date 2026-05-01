import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token


class TenantService:
    """Service for tenant operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, tenant_data: TenantCreate) -> Tenant:
        """Create a new tenant with initial user"""
        # Hash the password
        hashed_password = get_password_hash(tenant_data.password)

        # Create tenant
        tenant = Tenant(
            name=tenant_data.name,
            email=tenant_data.email,
            hashed_password=hashed_password,
            hotel_name=tenant_data.hotel_name,
            hotel_address=tenant_data.hotel_address,
            phone=tenant_data.phone,
        )
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)

        return tenant

    async def get_tenant_by_email(self, email: str) -> Optional[Tenant]:
        """Get tenant by email"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.email == email)
        )
        return result.scalar_one_or_none()

    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_tenant(self, tenant_id: str, update_data: TenantUpdate) -> Optional[Tenant]:
        """Update tenant profile"""
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(tenant, field, value)

        tenant.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(tenant)

        return tenant

    async def authenticate_tenant(self, email: str, password: str) -> Optional[Tenant]:
        """Authenticate tenant with email and password"""
        tenant = await self.get_tenant_by_email(email)
        if not tenant or not tenant.is_active:
            return None

        if not verify_password(password, tenant.hashed_password):
            return None

        return tenant

    async def create_tokens(self, tenant: Tenant) -> dict:
        """Create access and refresh tokens for tenant"""
        access_jti = str(uuid4())
        refresh_jti = str(uuid4())

        access_token = create_access_token({
            "sub": tenant.id,
            "tenant_id": tenant.id,
            "jti": access_jti,
            "type": "access"
        })

        refresh_token = create_refresh_token({
            "sub": tenant.id,
            "tenant_id": tenant.id,
            "jti": refresh_jti,
            "type": "refresh"
        })

        from app.core.config import get_settings
        settings = get_settings()

        from app.models import Session, RefreshToken

        # Create session record
        session = Session(
            tenant_id=tenant.id,
            user_id=None,  # Tenant-level session, not user-level
            token_jti=access_jti,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        )
        self.db.add(session)

        # Create refresh token record
        refresh_token_record = RefreshToken(
            tenant_id=tenant.id,
            user_id=None,
            token_jti=refresh_jti,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
        self.db.add(refresh_token_record)

        await self.db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh_tokens(self, refresh_token: str) -> Optional[dict]:
        """Refresh access token using refresh token"""
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            return None

        jti = payload.get("jti")
        tenant_id = payload.get("sub")

        from app.models import RefreshToken as RefreshTokenModel

        # Find the refresh token
        result = await self.db.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_jti == jti,
                RefreshTokenModel.tenant_id == tenant_id,
                RefreshTokenModel.is_revoked == False,
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record or token_record.expires_at < datetime.now(timezone.utc):
            return None

        # Get tenant
        tenant = await self.get_tenant_by_id(tenant_id)
        if not tenant or not tenant.is_active:
            return None

        # Revoke old refresh token
        token_record.is_revoked = True

        # Create new tokens
        return await self.create_tokens(tenant)

    async def revoke_session(self, jti: str, tenant_id: str) -> bool:
        """Revoke a session"""
        from app.models import Session

        result = await self.db.execute(
            select(Session).where(
                Session.token_jti == jti,
                Session.tenant_id == tenant_id
            )
        )
        session = result.scalar_one_or_none()

        if session:
            session.is_active = False
            await self.db.commit()
            return True
        return False

    async def revoke_all_sessions(self, tenant_id: str) -> int:
        """Revoke all sessions for a tenant"""
        from app.models import Session

        result = await self.db.execute(
            select(Session).where(
                Session.tenant_id == tenant_id,
                Session.is_active == True
            )
        )
        sessions = result.scalars().all()

        count = 0
        for session in sessions:
            session.is_active = False
            count += 1

        await self.db.commit()
        return count


def verify_tenant_password(tenant: Tenant, password: str) -> bool:
    """Verify tenant password"""
    return verify_password(password, tenant.hashed_password)


def hash_tenant_password(password: str) -> str:
    """Hash password for tenant"""
    return get_password_hash(password)