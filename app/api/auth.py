from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.core import get_db
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantLogin, TokenResponse, TenantResponse, TenantUpdate
from app.services.tenant_service import TenantService
from app.api.deps import get_current_tenant, get_user_agent, get_client_ip

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    tenant_data: TenantCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new tenant (hotel admin)"""
    tenant_service = TenantService(db)

    # Check if email already exists
    existing_tenant = await tenant_service.get_tenant_by_email(tenant_data.email)
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create tenant
    tenant = await tenant_service.create_tenant(tenant_data)

    # Create tokens
    tokens = await tenant_service.create_tokens(tenant)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        tenant=TenantResponse.model_validate(tenant),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: TenantLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Login as tenant (hotel admin)"""
    tenant_service = TenantService(db)

    tenant = await tenant_service.authenticate_tenant(
        credentials.email,
        credentials.password
    )

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create tokens
    tokens = await tenant_service.create_tokens(tenant)

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        tenant=TenantResponse.model_validate(tenant),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token"""
    refresh_token = refresh_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required",
        )

    tenant_service = TenantService(db)
    tokens = await tenant_service.refresh_tokens(refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get tenant for response
    from app.core.security import decode_token
    payload = decode_token(refresh_token)
    tenant = await tenant_service.get_tenant_by_id(payload.get("sub"))

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        tenant=TenantResponse.model_validate(tenant),
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Logout and revoke current session"""
    from app.core.security import decode_token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        jti = payload.get("jti")

        if jti:
            tenant_service = TenantService(db)
            await tenant_service.revoke_session(jti, current_tenant.id)

    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Logout from all sessions"""
    tenant_service = TenantService(db)
    count = await tenant_service.revoke_all_sessions(current_tenant.id)

    return {"message": f"Logged out from {count} sessions"}


# Profile routes
@router.get("/profile", response_model=TenantResponse)
async def get_profile(
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """Get current tenant profile"""
    return current_tenant


@router.patch("/profile", response_model=TenantResponse)
async def update_profile(
    update_data: TenantUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update tenant profile"""
    tenant_service = TenantService(db)
    updated_tenant = await tenant_service.update_tenant(current_tenant.id, update_data)
    return updated_tenant


@router.post("/profile/password")
async def change_password(
    password_data: dict,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Change tenant password"""
    from app.core.security import get_password_hash, verify_password

    current_password = password_data.get("current_password")
    new_password = password_data.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both current_password and new_password are required",
        )

    if not verify_password(current_password, current_tenant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_tenant.hashed_password = get_password_hash(new_password)
    current_tenant.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Password changed successfully"}