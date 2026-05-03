"""Webhook API Routes - Baileys Gateway integration"""

import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core import get_db
from app.core.config import get_settings
from app.models import Tenant
from app.services.whatsapp_service import WhatsAppService
from app.services.agent_service import AgentService
from app.services.baileys_client import BaileysGatewayClient
from app.schemas.whatsapp import WhatsAppMessageCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhooks"])
settings = get_settings()


class WebhookResponse(BaseModel):
    message: str
    agent_response: Optional[str] = None
    sources: Optional[list[str]] = None
    success: bool = True


# =============================================================================
# Message Parsing
# =============================================================================

def parse_baileys_message(payload: dict) -> Optional[tuple[str, str, dict]]:
    """
    Parse Baileys gateway webhook payload.
    Returns (from_number, message_text, message_key) or None if not a valid inbound message.

    Payload format:
    {
        "event": "onMessage",
        "session": "session_name",
        "data": {
            "key": { "remoteJid": "...", "fromMe": false, ... },
            "message": { "conversation": "Hello!" },
            "pushName": "Contact Name"
        }
    }
    """
    event = payload.get("event", "")
    if event not in ("onMessage", "onMessageReceived"):
        return None

    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None

    key = data.get("key", {})
    message = data.get("message", {})

    # Skip outgoing messages
    if key.get("fromMe", False):
        return None

    text = _extract_message_text(message)
    if not text:
        return None

    remote_jid = key.get("remoteJid", "")
    from_number = _extract_phone_from_jid(remote_jid)

    if not from_number:
        sender = data.get("sender") or payload.get("sender")
        if sender:
            from_number = _extract_phone_from_jid(sender)

    if not from_number:
        from_number = "unknown"

    return (from_number, text, key)


def _extract_message_text(message: dict) -> str:
    """Extract text content from a Baileys message object."""
    if not isinstance(message, dict):
        return ""

    # Plain conversation
    conv = message.get("conversation", "")
    if conv:
        return conv

    # Extended text message
    ext = message.get("extendedTextMessage", {})
    if isinstance(ext, dict):
        text = ext.get("text", "")
        if text:
            return text

    # Image with caption
    img = message.get("imageMessage", {})
    if isinstance(img, dict):
        caption = img.get("caption", "")
        if caption:
            return caption

    # Video with caption
    vid = message.get("videoMessage", {})
    if isinstance(vid, dict):
        caption = vid.get("caption", "")
        if caption:
            return caption

    return ""


def _extract_phone_from_jid(jid: str) -> str:
    """Extract phone number from WhatsApp JID."""
    if not jid:
        return ""
    phone = jid.split("@")[0] if "@" in jid else jid
    if ":" in phone and phone.split(":")[0].isdigit():
        phone = phone.split(":")[0]
    return phone


# =============================================================================
# Tenant Resolution
# =============================================================================

async def resolve_webhook_tenant(request: Request, db: AsyncSession) -> Optional[Tenant]:
    """Resolve tenant from webhook request via tenant_id query param or fallback."""
    # Try query param first
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if tenant:
            logger.info(f"Webhook resolved to tenant: {tenant.name} ({tenant.id})")
            return tenant

    # Fall back to configured tenant
    if settings.webhook_whatsapp_tenant_id:
        result = await db.execute(
            select(Tenant).where(Tenant.id == settings.webhook_whatsapp_tenant_id)
        )
        return result.scalar_one_or_none()

    # Fall back to first tenant
    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    logger.info(f"Webhook falling back to first tenant: {tenant.name if tenant else 'NONE'}")
    return tenant


# =============================================================================
# Message Handler
# =============================================================================

async def handle_whatsapp_message(
    tenant: Tenant,
    from_number: str,
    message_content: str,
    msg_id: str,
    db: AsyncSession,
) -> WebhookResponse:
    """Process a WhatsApp message and generate AI response."""
    whatsapp_service = WhatsAppService(db)

    # Record inbound message
    message_data = WhatsAppMessageCreate(
        message_id=msg_id,
        direction="inbound",
        from_number=from_number,
        content=message_content,
    )
    await whatsapp_service.record_message(tenant.id, message_data)
    logger.info(
        "Inbound WhatsApp stored tenant=%s from=%s len=%s",
        tenant.id,
        from_number,
        len(message_content),
    )

    # Generate agent response via RAG
    from app.schemas.agent import AgentTestRequest

    agent_service = AgentService(db)
    test_request = AgentTestRequest(
        question=message_content,
        context=f"WhatsApp message from {from_number}",
    )

    try:
        result = await agent_service.test_agent(tenant.id, test_request)
    except Exception:
        logger.exception("Agent failed for tenant=%s", tenant.id)
        return WebhookResponse(message="", success=False)

    # Record outbound response
    response_data = WhatsAppMessageCreate(
        message_id=str(uuid4()),
        direction="outbound",
        from_number="agent",
        to_number=from_number,
        content=result.answer,
        agent_response=result.answer,
        wiki_sources={"sources": result.sources} if result.sources else None,
        web_search_used=result.web_search_used,
    )
    await whatsapp_service.record_message(tenant.id, response_data)

    # Send reply via Baileys Gateway
    await _send_whatsapp_reply(tenant.id, from_number, result.answer)

    return WebhookResponse(
        message=result.answer,
        agent_response=result.answer,
        sources=result.sources,
        success=True,
    )


async def _send_whatsapp_reply(tenant_id: str, to_number: str, message: str):
    """Send WhatsApp reply via Baileys Gateway."""
    try:
        hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
        session_name = f"inika-{hash_suffix}"
        client = BaileysGatewayClient(session_name=session_name)
        await client.send_message(to_number, message)
        await client.close()
    except Exception:
        logger.exception("Failed to send WhatsApp reply")


# =============================================================================
# Baileys Gateway Webhook Endpoint
# =============================================================================

@router.post("/whatsapp-baileys", response_model=WebhookResponse)
async def receive_baileys_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive WhatsApp messages from Baileys Gateway.
    The gateway sends webhooks when messages are received from guests.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    logger.info(f"Baileys webhook received: {payload.get('event', 'unknown')}")

    parsed = parse_baileys_message(payload)
    if not parsed:
        logger.info(f"Baileys webhook: no valid message parsed (event: {payload.get('event')})")
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    tenant = await resolve_webhook_tenant(request, db)
    if not tenant:
        logger.warning("Webhook: no tenant found for WhatsApp message")
        return WebhookResponse(message="No tenant configured", success=False)

    return await handle_whatsapp_message(
        tenant=tenant,
        from_number=from_number,
        message_content=message_content,
        msg_id=msg_id,
        db=db,
    )


# =============================================================================
# Health & Status
# =============================================================================

@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint."""
    return {"status": "healthy", "service": "inika-webhook"}


@router.get("/status/{tenant_id}")
async def get_webhook_status(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get WhatsApp and Agent status for a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    whatsapp_service = WhatsAppService(db)
    agent_service = AgentService(db)

    whatsapp_status = await whatsapp_service.get_status(tenant_id)
    agent_status = await agent_service.get_agent_status(tenant_id)

    return {
        "tenant_id": tenant_id,
        "whatsapp": {
            "is_connected": whatsapp_status.is_connected,
            "status": whatsapp_status.status,
            "phone_number": whatsapp_status.phone_number,
        },
        "agent": {
            "is_configured": agent_status["is_configured"],
            "has_system_prompt": agent_status["has_system_prompt"],
        },
    }
