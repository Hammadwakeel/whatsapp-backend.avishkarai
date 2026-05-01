from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db, decode_token
from app.models import Tenant
from app.services.tenant_service import TenantService

security = HTTPBearer()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Extract tenant from JWT token"""
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing tenant_id",
        )

    tenant_service = TenantService(db)
    tenant = await tenant_service.get_tenant_by_id(tenant_id)

    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found or inactive",
        )

    return tenant


async def get_optional_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[Tenant]:
    """Extract tenant from request if authenticated, otherwise return None"""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        return None

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        return None

    tenant_service = TenantService(db)
    return await tenant_service.get_tenant_by_id(tenant_id)


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    return request.client.host if request.client else None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request"""
    return request.headers.get("user-agent")


class TenantContext:
    """Thread-local storage for current tenant"""

    def __init__(self):
        self._tenant_id: Optional[str] = None
        self._db: Optional[AsyncSession] = None

    def set(self, tenant_id: str, db: AsyncSession):
        self._tenant_id = tenant_id
        self._db = db

    def clear(self):
        self._tenant_id = None
        self._db = None

    @property
    def tenant_id(self) -> Optional[str]:
        return self._tenant_id

    @property
    def db(self) -> Optional[AsyncSession]:
        return self._db


# Global tenant context
tenant_context = TenantContext()