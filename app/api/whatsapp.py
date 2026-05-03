"""WhatsApp API Routes - WAHA / Evolution API Integration"""

import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.core.config import get_settings
from app.models import Tenant, SessionStatus
from app.schemas.whatsapp import (
    WhatsAppSessionResponse, WhatsAppStatusResponse,
    WhatsAppMessageResponse, MessageListResponse,
    WhatsAppSendRequest, WhatsAppMessageCreate,
)
from app.services.whatsapp_service import WhatsAppService
from app.services.sse_manager import sse_manager, create_sse_response
from app.api.deps import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
settings = get_settings()


def get_whatsapp_client(tenant_id: str):
    """Get the appropriate WhatsApp client (Baileys Gateway, WAHA, or Evolution)."""
    import hashlib

    # Create per-tenant session name (same format for all gateways)
    hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
    session_name = f"inika-{hash_suffix}"

    # Priority: Baileys Gateway > WAHA > Evolution
    if settings.baileys_gateway_url:
        from app.services.baileys_client import BaileysGatewayClient
        return BaileysGatewayClient(session_name=session_name)
    elif settings.waha_url:
        from app.services.waha_client import WAHAClient
        return WAHAClient(session_name=session_name)
    else:
        from app.services.evolution_client import EvolutionClient
        from app.services.whatsapp_service import WhatsAppService
        whatsapp_service = WhatsAppService(None)
        instance_name = whatsapp_service._get_tenant_instance_name(tenant_id)
        return EvolutionClient(instance_name=instance_name)


def get_tenant_webhook_url(tenant_id: str, request: Request = None) -> str:
    """Build the tenant-specific webhook URL for WhatsApp gateway.

    The gateway sends webhooks to this URL when messages are received.
    The tenant_id query param allows routing to the correct tenant.
    """
    import os

    # Determine which webhook endpoint to use based on configured gateway
    if settings.baileys_gateway_url:
        base_path = "/webhook/whatsapp-baileys"
    elif settings.waha_url:
        base_path = "/webhook/whatsapp-waha"
    else:
        base_path = "/webhook/whatsapp"

    # If explicit webhook URL is set, use it
    if settings.evolution_webhook_url:
        return f"{settings.evolution_webhook_url.rstrip('/')}{base_path}?tenant_id={tenant_id}"

    # Check for Docker environment
    in_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER")

    if not in_docker:
        base_url = settings.api_base_url or "http://localhost:8000"
        return f"{base_url.rstrip('/')}{base_path}?tenant_id={tenant_id}"

    # Docker environment - use host.docker.internal
    host_url = "http://host.docker.internal:8000"
    return f"{host_url}{base_path}?tenant_id={tenant_id}"


@router.get("/status", response_model=WhatsAppStatusResponse)
async def get_whatsapp_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get WhatsApp connection status.
    Uses WAHA if configured, otherwise Evolution API.
    """
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)

    # Get status from gateway
    evolution_status = await client.get_connection_status()

    # Get local session for comparison
    session = await whatsapp_service.get_session(current_tenant.id)
    old_status = session.status if session else None
    new_status = evolution_status.get("status", SessionStatus.DISCONNECTED.value)

    # Update local session if connected
    if evolution_status.get("connected"):
        session = await whatsapp_service.get_or_create_session(current_tenant.id)
        session.status = SessionStatus.CONNECTED.value
        if not session.connected_at:
            session.connected_at = datetime.now(timezone.utc)

        # Store phone number if available
        if evolution_status.get("phone_number"):
            session.phone_number = evolution_status["phone_number"]
        if evolution_status.get("display_name"):
            session.display_name = evolution_status["display_name"]

        await db.commit()

    # Detect state changes and broadcast
    if old_status != new_status and old_status is not None:
        logger.info(f"WhatsApp state change for tenant={current_tenant.id}: {old_status} -> {new_status}")
        await sse_manager.broadcast_connection_state(current_tenant.id, new_status)

        # If disconnected unexpectedly
        if new_status in ("DISCONNECTED", "DISCONNECTED_BY_OWNER") and old_status == "CONNECTED":
            logger.warning(f"Unexpected WhatsApp disconnect for tenant={current_tenant.id}")
            await sse_manager.broadcast(current_tenant.id, "session_disconnected", {
                "message": "WhatsApp session was disconnected. Please scan QR code to reconnect.",
                "old_state": old_status,
                "action": "reconnect_required"
            })

    # Get QR code if available
    qrcode = evolution_status.get("qr_code")
    if not evolution_status.get("connected") and not qrcode:
        qrcode = await client.get_qr_code_image()

    # Fallback to stored QR
    if not qrcode and session and session.qr_code:
        qrcode = session.qr_code

    return WhatsAppStatusResponse(
        is_connected=evolution_status.get("connected", False),
        status=new_status,
        qrcode=qrcode,
        phone_number=evolution_status.get("phone_number") or (session.phone_number if session else None),
        display_name=evolution_status.get("display_name") or (session.display_name if session else None),
        connected_at=session.connected_at if session else None,
        last_activity=session.last_activity if session else None,
        message_count=await whatsapp_service.get_message_count(current_tenant.id),
        local_session_id=session.id if session else None,
    )


@router.post("/connect")
async def connect_whatsapp(
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect WhatsApp by generating QR code.
    Uses WAHA if configured, otherwise Evolution API.
    """
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)
    webhook_url = get_tenant_webhook_url(current_tenant.id, request)

    # Check current status
    status = await client.get_connection_status()

    if status.get("connected"):
        await whatsapp_service.update_status(
            current_tenant.id,
            status=SessionStatus.CONNECTED.value
        )
        return {
            "status": "connected",
            "message": "WhatsApp is already connected",
            "connected": True
        }

    # Get or create local session
    session = await whatsapp_service.get_or_create_session(current_tenant.id)

    # Generate QR code
    qr_result = await client.generate_qr_code(webhook_url=webhook_url)

    if qr_result.get("success") and qr_result.get("qr_code"):
        qr_code = qr_result["qr_code"]

        # Store QR code
        await whatsapp_service.set_qr_code(
            current_tenant.id,
            qr_code=qr_code,
            expires_at=datetime.now(timezone.utc).replace(second=0)
        )

        return {
            "status": "qr_available",
            "qr_code": qr_code,
            "message": "Scan this QR code with WhatsApp",
            "local_session_id": session.id
        }

    if qr_result.get("already_connected"):
        await loadAll()
        return {
            "status": "connected",
            "message": "WhatsApp is already connected",
            "connected": True
        }

    return {
        "status": "waiting",
        "message": qr_result.get("error") or qr_result.get("details") or "Generating QR code...",
        "gateway": "WAHA" if settings.waha_url else "Evolution",
    }


@router.post("/disconnect")
async def disconnect_whatsapp(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect WhatsApp session."""
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)

    # Disconnect via gateway
    await client.logout()

    # Update local status
    await whatsapp_service.update_status(
        current_tenant.id,
        status=SessionStatus.DISCONNECTED.value
    )

    # Broadcast disconnect
    await sse_manager.broadcast_connection_state(current_tenant.id, "DISCONNECTED")

    return {"message": "WhatsApp disconnected successfully"}


@router.get("/events")
async def whatsapp_sse_events(
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Server-Sent Events (SSE) endpoint for real-time WhatsApp updates.
    """
    return create_sse_response(current_tenant.id)


@router.post("/refresh-webhook")
async def refresh_whatsapp_webhook(
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Refresh webhook configuration for WhatsApp gateway."""
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)
    webhook_url = get_tenant_webhook_url(current_tenant.id, request)

    # Re-create session with new webhook
    if hasattr(client, 'create_session'):
        result = await client.create_session(webhook_url=webhook_url)
        if result.get("success"):
            return {
                "status": "configured",
                "webhook_url": webhook_url,
                "message": "Webhook URL configured successfully",
            }

    return {
        "status": "configured",
        "webhook_url": webhook_url,
        "message": "Webhook URL updated",
    }


@router.get("/reset-session")
async def reset_whatsapp_session(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Reset WhatsApp session and generate new QR code.
    """
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)
    webhook_url = get_tenant_webhook_url(current_tenant.id)

    # Logout first
    await client.logout()

    # Update local session
    session = await whatsapp_service.update_status(
        current_tenant.id,
        status=SessionStatus.DISCONNECTED.value
    )

    # Clear session data
    session.qr_code = None
    session.qr_expires_at = None
    session.phone_number = None
    session.display_name = None
    session.connected_at = None
    session.error_message = "Session reset by user"
    await db.commit()

    # Broadcast reset
    await sse_manager.broadcast_connection_state(current_tenant.id, "RESET")

    # Generate new QR
    qr_result = await client.generate_qr_code(webhook_url=webhook_url)

    if qr_result.get("success") and qr_result.get("qr_code"):
        await whatsapp_service.set_qr_code(
            current_tenant.id,
            qr_code=qr_result["qr_code"],
            expires_at=datetime.now(timezone.utc).replace(second=0)
        )
        return {
            "status": "qr_available",
            "qr_code": qr_result["qr_code"],
            "message": "Session reset. Scan new QR code with WhatsApp",
        }

    return {
        "status": "waiting",
        "message": "Session reset. Generating QR code...",
    }


@router.get("/session", response_model=WhatsAppSessionResponse)
async def get_whatsapp_session(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get WhatsApp session details."""
    whatsapp_service = WhatsAppService(db)
    session = await whatsapp_service.get_or_create_session(current_tenant.id)
    return session


@router.get("/messages", response_model=MessageListResponse)
async def get_messages(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=300),
    direction: str = Query(None, pattern="^(inbound|outbound)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Get message history."""
    whatsapp_service = WhatsAppService(db)
    messages, total = await whatsapp_service.get_messages(
        current_tenant.id,
        page=page,
        page_size=page_size,
        direction=direction,
        order=order,
    )
    return MessageListResponse(
        messages=[WhatsAppMessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/send")
async def send_whatsapp_message(
    body: WhatsAppSendRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send a text message via WhatsApp gateway."""
    whatsapp_service = WhatsAppService(db)
    client = get_whatsapp_client(current_tenant.id)

    send_result = await client.send_message(body.to, body.message)

    if not send_result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=send_result.get("error") or send_result.get("details") or "Failed to send message",
        )

    session = await whatsapp_service.get_session(current_tenant.id)
    out_from = session.phone_number if session and session.phone_number else "hotel"

    msg_in = WhatsAppMessageCreate(
        session_id=session.id if session else None,
        message_id=send_result.get("message_id"),
        direction="outbound",
        from_number=out_from,
        to_number=body.to.strip(),
        content=body.message,
    )
    await whatsapp_service.record_message(current_tenant.id, msg_in)

    return {
        "message_id": send_result.get("message_id"),
        "status": "sent",
    }