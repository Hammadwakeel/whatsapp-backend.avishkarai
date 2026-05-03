"""WhatsApp API Routes - Evolution API Integration"""

import asyncio
import base64
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
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
from app.services.evolution_client import EvolutionClient
from app.services.sse_manager import sse_manager, create_sse_response
from app.api.deps import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
settings = get_settings()


def get_tenant_evolution_client(whatsapp_service: WhatsAppService, tenant_id: str) -> EvolutionClient:
    """Create a tenant-specific Evolution client for session isolation.

    Each tenant gets their own Evolution instance, ensuring WhatsApp sessions
    persist independently per tenant.
    """
    instance_name = whatsapp_service._get_tenant_instance_name(tenant_id)
    return EvolutionClient(instance_name=instance_name)


@router.get("/status", response_model=WhatsAppStatusResponse)
async def get_whatsapp_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get WhatsApp connection status from Evolution API.
    Uses tenant-specific instance for session isolation.
    Broadcasts state changes via SSE.
    """
    whatsapp_service = WhatsAppService(db)
    evolution_client = get_tenant_evolution_client(whatsapp_service, current_tenant.id)

    # Get real-time status from Evolution API
    evolution_status = await evolution_client.get_connection_status()

    # Get current session state for comparison
    session = await whatsapp_service.get_session(current_tenant.id)
    old_status = session.status if session else None
    new_status = evolution_status.get("status", SessionStatus.DISCONNECTED.value)

    # Update local session if connected - but only update connected_at once (don't spam DB on every poll)
    if evolution_status.get("connected"):
        session = await whatsapp_service.get_or_create_session(current_tenant.id)
        session.status = SessionStatus.CONNECTED.value
        # Only update connected_at if not already set (prevents constant DB writes)
        if not session.connected_at:
            session.connected_at = datetime.now(timezone.utc)
        await db.commit()

    # Detect state changes and broadcast via SSE
    if old_status != new_status and old_status is not None:
        logger.info(f"WhatsApp state change for tenant={current_tenant.id}: {old_status} -> {new_status}")
        await sse_manager.broadcast_connection_state(current_tenant.id, new_status)

        # If disconnected unexpectedly, trigger auto-reset flow
        if new_status in ("DISCONNECTED", "CLOSE", "CLOSED", "ERROR") and old_status == "CONNECTED":
            logger.warning(f"Unexpected WhatsApp disconnect for tenant={current_tenant.id}")
            await sse_manager.broadcast(current_tenant.id, "session_disconnected", {
                "message": "WhatsApp session was disconnected. Please scan QR code to reconnect.",
                "old_state": old_status,
                "action": "reconnect_required"
            })

    # Get local session for QR code
    session = await whatsapp_service.get_session(current_tenant.id)

    # connectionState often omits QR (Evolution v2); fetch from qrCode/connect endpoints
    qrcode = evolution_status.get("qr_code")
    if not evolution_status.get("connected"):
        if not qrcode:
            qrcode = await evolution_client.poll_live_qr()
        if not qrcode and session and session.qr_code:
            qrcode = session.qr_code
    else:
        qrcode = qrcode or (session.qr_code if session else None)

    pairing_code = evolution_client.get_pairing_code()
    evolution_detail = None
    if not qrcode and not evolution_status.get("connected"):
        evolution_detail = evolution_client.evolution_user_hint()

    return WhatsAppStatusResponse(
        is_connected=evolution_status.get("connected", False),
        status=evolution_status.get("status", SessionStatus.DISCONNECTED.value),
        qrcode=qrcode,
        phone_number=session.phone_number if session else None,
        display_name=session.display_name if session else None,
        connected_at=session.connected_at if session else None,
        last_activity=session.last_activity if session else None,
        message_count=await whatsapp_service.get_message_count(current_tenant.id),
        local_session_id=session.id if session else None,
        pairing_code=pairing_code,
        evolution_detail=evolution_detail,
    )


@router.post("/connect")
async def connect_whatsapp(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect WhatsApp by generating QR code.
    Returns the QR code image as base64.
    Uses tenant-specific instance for session isolation.
    """
    whatsapp_service = WhatsAppService(db)
    evolution_client = get_tenant_evolution_client(whatsapp_service, current_tenant.id)

    # Check current status
    status = await evolution_client.get_connection_status()

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
    qr_result = await evolution_client.generate_qr_code()

    if qr_result.get("success") and qr_result.get("qr_code"):
        qr_code = qr_result["qr_code"]

        # Store QR code in database
        await whatsapp_service.set_qr_code(
            current_tenant.id,
            qr_code=qr_code,
            expires_at=datetime.now(timezone.utc).replace(second=0)  # QR expires quickly
        )

        # If QR is base64 image, return it directly
        if isinstance(qr_code, str) and (qr_code.startswith("data:image") or len(qr_code) > 100):
            return {
                "status": "qr_available",
                "qr_code": qr_code,
                "message": "Scan this QR code with WhatsApp",
                "local_session_id": session.id
            }

        # If QR is a URL or needs to be fetched as image
        qr_image = await evolution_client.get_qr_code_image()
        if qr_image:
            # Update with actual image
            await whatsapp_service.set_qr_code(
                current_tenant.id,
                qr_code=qr_image,
                expires_at=datetime.now(timezone.utc).replace(second=0)
            )
            return {
                "status": "qr_available",
                "qr_code": qr_image,
                "message": "Scan this QR code with WhatsApp",
                "local_session_id": session.id
            }

        # Return the QR code as-is if it's text-based
        return {
            "status": "qr_available",
            "qr_code": qr_code,
            "message": "Scan this QR code with WhatsApp",
            "local_session_id": session.id
        }

    # Return waiting status if QR generation is pending
    detail = qr_result.get("details") or evolution_client.evolution_user_hint()
    return {
        "status": "waiting",
        "message": qr_result.get("error") or qr_result.get("message") or "Generating QR code...",
        "evolution_url": settings.evolution_url,
        "instance_name": evolution_client.instance_name,
        "local_session_id": session.id,
        "evolution_detail": detail,
    }


@router.post("/disconnect")
async def disconnect_whatsapp(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect WhatsApp session for this tenant only."""
    whatsapp_service = WhatsAppService(db)
    evolution_client = get_tenant_evolution_client(whatsapp_service, current_tenant.id)

    # Disconnect via Evolution API
    await evolution_client.logout()

    # Update local status
    await whatsapp_service.update_status(
        current_tenant.id,
        status=SessionStatus.DISCONNECTED.value
    )

    # Broadcast disconnect event via SSE
    await sse_manager.broadcast_connection_state(current_tenant.id, "DISCONNECTED")

    return {"message": "WhatsApp disconnected successfully"}


@router.get("/events")
async def whatsapp_sse_events(
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
):
    """
    Server-Sent Events (SSE) endpoint for real-time WhatsApp updates.
    Replace polling with SSE for instant updates on:
    - Connection status changes
    - New incoming/outgoing messages
    - QR code generation
    """
    return create_sse_response(current_tenant.id)


@router.get("/reset-session")
async def reset_whatsapp_session(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Reset the WhatsApp session and start fresh.
    This will:
    1. Logout from Evolution API
    2. Clear local session data
    3. Broadcast disconnect event
    4. Generate new QR code
    """
    whatsapp_service = WhatsAppService(db)
    evolution_client = get_tenant_evolution_client(whatsapp_service, current_tenant.id)

    # Logout from Evolution
    await evolution_client.logout()

    # Update local status to disconnected
    session = await whatsapp_service.update_status(
        current_tenant.id,
        status=SessionStatus.DISCONNECTED.value
    )

    # Clear QR code and related data
    session.qr_code = None
    session.qr_expires_at = None
    session.phone_number = None
    session.display_name = None
    session.connected_at = None
    session.error_message = "Session reset by user"
    await db.commit()

    # Broadcast reset event
    await sse_manager.broadcast_connection_state(current_tenant.id, "RESET")

    # Generate new QR code
    qr_result = await evolution_client.generate_qr_code()

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

    detail = qr_result.get("details") or evolution_client.evolution_user_hint()
    return {
        "status": "waiting",
        "message": "Session reset. Generating QR code...",
        "evolution_detail": detail,
    }


@router.get("/session", response_model=WhatsAppSessionResponse)
async def get_whatsapp_session(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get WhatsApp session details"""
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
    """Get message history"""
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
    """Send a text message via Evolution (manual reply from dashboard)."""
    whatsapp_service = WhatsAppService(db)
    evolution_client = get_tenant_evolution_client(whatsapp_service, current_tenant.id)
    send_result = await evolution_client.send_message(body.to, body.message)
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