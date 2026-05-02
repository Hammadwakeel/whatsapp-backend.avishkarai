"""WhatsApp API Routes - Evolution API Integration"""

import base64
import qrcode
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.core.config import get_settings
from app.models import Tenant, SessionStatus
from app.schemas.whatsapp import (
    WhatsAppSessionResponse, WhatsAppStatusResponse, QRCodeResponse,
    WhatsAppMessageResponse, MessageListResponse,
)
from app.services.whatsapp_service import WhatsAppService
from app.services.evolution_client import evolution_client
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
settings = get_settings()


@router.get("/status", response_model=WhatsAppStatusResponse)
async def get_whatsapp_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get WhatsApp connection status from Evolution API.
    """
    whatsapp_service = WhatsAppService(db)

    # Get real-time status from Evolution API
    evolution_status = await evolution_client.get_connection_status()

    # Update local session if connected
    if evolution_status.get("connected"):
        session = await whatsapp_service.get_or_create_session(current_tenant.id)
        session.status = SessionStatus.CONNECTED.value
        session.connected_at = datetime.now(timezone.utc)
        await db.commit()

    return await whatsapp_service.get_status(current_tenant.id)


@router.post("/connect")
async def connect_whatsapp(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect WhatsApp by generating QR code.
    Returns the QR code image as base64.
    """
    whatsapp_service = WhatsAppService(db)

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

        # If QR is base64, return it directly
        if isinstance(qr_code, str) and len(qr_code) > 100:
            return {
                "status": "qr_available",
                "qr_code": qr_code,
                "message": "Scan this QR code with WhatsApp",
                "local_session_id": session.id
            }

        # If QR is a URL or needs to be fetched as image
        qr_image = await evolution_client.get_qr_code_image()
        if qr_image:
            return {
                "status": "qr_available",
                "qr_code": qr_image,
                "message": "Scan this QR code with WhatsApp",
                "local_session_id": session.id
            }

    # Return waiting status if QR generation is pending
    return {
        "status": "waiting",
        "message": qr_result.get("message", "Generating QR code..."),
        "evolution_url": settings.evolution_url,
        "instance_name": settings.evolution_instance_name,
        "local_session_id": session.id
    }


@router.get("/qr")
async def get_qr_code_info(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get QR code for WhatsApp pairing.
    Returns QR code as base64 image or URL.
    """
    # Check if already connected
    status = await evolution_client.get_connection_status()

    if status.get("connected"):
        return {
            "status": "connected",
            "message": "WhatsApp is already connected",
            "qr_code": None
        }

    # Generate QR code
    qr_result = await evolution_client.generate_qr_code()

    if qr_result.get("success"):
        qr_code = qr_result.get("qr_code")

        # Return QR code data
        return {
            "status": "qr_available" if qr_code else "waiting",
            "qr_code": qr_code,
            "qr_image": await evolution_client.get_qr_code_image(),
            "message": qr_result.get("message", "QR code ready")
        }

    return {
        "status": "error",
        "message": qr_result.get("error", "Failed to generate QR"),
        "details": qr_result
    }


@router.get("/qr/image")
async def get_qr_code_image(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get QR code as PNG image.
    """
    # Check if connected
    status = await evolution_client.get_connection_status()

    if status.get("connected"):
        return JSONResponse(
            content={"status": "connected", "message": "WhatsApp is already connected"},
            status_code=400
        )

    # Get QR code image from Evolution API
    qr_image = await evolution_client.get_qr_code_image()

    if qr_image:
        # Decode base64 and return as PNG
        try:
            image_data = base64.b64decode(qr_image)
            img_buffer = BytesIO(image_data)
            return StreamingResponse(
                img_buffer,
                media_type="image/png",
                headers={"Content-Disposition": "inline; filename=whatsapp-qr.png"}
            )
        except Exception as e:
            pass

    # Fallback: Generate QR code and return as image
    qr_result = await evolution_client.generate_qr_code()

    if qr_result.get("success") and qr_result.get("qr_code"):
        qr_data = qr_result["qr_code"]

        # If it's a base64 image, decode and return
        if len(qr_data) > 100:
            try:
                image_data = base64.b64decode(qr_data)
                img_buffer = BytesIO(image_data)
                return StreamingResponse(
                    img_buffer,
                    media_type="image/png",
                    headers={"Content-Disposition": "inline; filename=whatsapp-qr.png"}
                )
            except:
                pass

    # Last resort: Return placeholder with instructions
    qr_text = f"EVOLUTION:{settings.evolution_instance_name}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    return StreamingResponse(
        img_buffer,
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=whatsapp-qr-placeholder.png"}
    )


@router.post("/disconnect")
async def disconnect_whatsapp(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect WhatsApp session"""
    whatsapp_service = WhatsAppService(db)

    # Disconnect via Evolution API
    await evolution_client.logout()

    # Update local status
    await whatsapp_service.update_status(
        current_tenant.id,
        status=SessionStatus.DISCONNECTED.value
    )

    return {"message": "WhatsApp disconnected successfully"}


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
    page_size: int = Query(50, ge=1, le=100),
    direction: str = Query(None, pattern="^(inbound|outbound)$"),
):
    """Get message history"""
    whatsapp_service = WhatsAppService(db)
    messages, total = await whatsapp_service.get_messages(
        current_tenant.id,
        page=page,
        page_size=page_size,
        direction=direction
    )
    return MessageListResponse(
        messages=[WhatsAppMessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size
    )


# =============================================================================
# WEBHOOK ENDPOINT - For Evolution API to send messages to our backend
# =============================================================================

@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint for receiving WhatsApp messages from Evolution API.

    Configure this URL in Evolution API:
    {your-backend-url}/whatsapp/webhook
    """
    try:
        payload = await request.json()

        # Process the incoming message
        message_data = await evolution_client.receive_webhook(payload)

        if message_data.get("processed"):
            whatsapp_service = WhatsAppService(db)

            # Record the inbound message
            await whatsapp_service.record_message(
                tenant_id=None,  # Will be determined by phone number or default tenant
                direction="inbound",
                from_number=message_data["from"],
                content=message_data["message"],
                message_id=message_data.get("message_id"),
                sender_name=message_data.get("push_name")
            )

            # TODO: Route to AI agent and get response
            # This will be handled by the AI agent integration

        return {"status": "ok", "processed": message_data.get("processed")}

    except Exception as e:
        return {"status": "error", "message": str(e)}