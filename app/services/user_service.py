import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, UserHistory, Session, RefreshToken
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token, decode_token

# Note: For multi-tenant hotel platform, authentication is tenant-based (Tenant model)
# The User model is kept for future use if sub-users are needed per tenant
# For now, all operations use TenantService for authentication


class HistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant_history(self, tenant_id: str, limit: int = 50, offset: int = 0) -> tuple[list[UserHistory], int]:
        """Get history entries for a tenant"""
        result = await self.db.execute(
            select(UserHistory)
            .where(UserHistory.tenant_id == tenant_id)
            .order_by(UserHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        entries = list(result.scalars().all())

        count_result = await self.db.execute(
            select(UserHistory).where(UserHistory.tenant_id == tenant_id)
        )
        total = len(count_result.scalars().all())

        return entries, total


class SessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tenant_sessions(self, tenant_id: str) -> list[Session]:
        """Get active sessions for a tenant"""
        result = await self.db.execute(
            select(Session)
            .where(Session.tenant_id == tenant_id, Session.is_active == True)
            .order_by(Session.created_at.desc())
        )
        return list(result.scalars().all())

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions for all tenants"""
        result = await self.db.execute(
            update(Session)
            .where(Session.expires_at < datetime.now(timezone.utc), Session.is_active == True)
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount

    async def revoke_session(self, jti: str, tenant_id: str) -> bool:
        """Revoke a specific session"""
        result = await self.db.execute(
            select(Session).where(Session.token_jti == jti, Session.tenant_id == tenant_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
            await self.db.commit()
            return True
        return False

    async def revoke_all_sessions(self, tenant_id: str) -> int:
        """Revoke all sessions for a tenant"""
        result = await self.db.execute(
            update(Session)
            .where(Session.tenant_id == tenant_id, Session.is_active == True)
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount