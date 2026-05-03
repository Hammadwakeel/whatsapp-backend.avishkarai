"""Webhook API Routes - For WAHA, Evolution API and external integrations"""

import logging
from typing import Any, Optional

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
from app.services.sse_manager import sse_manager
from app.schemas.whatsapp import WhatsAppMessageCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhooks"])
settings = get_settings()


class WebhookMessageRequest(BaseModel):
    """Incoming message format from WhatsApp gateway"""
    session_id: str
    message_id: Optional[str] = None
    from_number: str
    to_number: Optional[str] = None
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[dict] = None


class WebhookResponse(BaseModel):
    """Response to send back"""
    message: str
    agent_response: Optional[str] = None
    sources: Optional[list[str]] = None
    success: bool = True


# =============================================================================
# WAHA Webhook Handler
# =============================================================================

def parse_waha_message(payload: dict) -> Optional[tuple[str, str, dict]]:
    """
    Parse WAHA webhook payload.
    Returns (from_number, message_text, message_data) or None if not a valid message.

    WAHA sends payloads in format:
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

    # Extract message
    key = data.get("key", {})
    message = data.get("message", {})

    # Skip outgoing messages
    if key.get("fromMe", False):
        return None

    # Extract text from message
    text = extract_message_text(message)
    if not text:
        return None

    # Extract sender
    remote_jid = key.get("remoteJid", "")
    from_number = extract_phone_from_jid(remote_jid)

    # Alternative: check sender at root level
    if not from_number:
        sender = data.get("sender") or payload.get("sender")
        if sender:
            from_number = extract_phone_from_jid(sender)

    if not from_number:
        from_number = "unknown"

    return (from_number, text, key)


def extract_message_text(message: dict) -> str:
    """Extract text from WAHA message object."""
    if isinstance(message, dict):
        # Conversation
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


def extract_phone_from_jid(jid: str) -> str:
    """Extract phone number from WhatsApp JID."""
    if not jid:
        return ""
    # Strip @s.whatsapp.net or @g.us
    phone = jid.split("@")[0] if "@" in jid else jid
    # Handle phone:number format (device linking)
    if ":" in phone and phone.split(":")[0].isdigit():
        phone = phone.split(":")[0]
    return phone


# =============================================================================
# Evolution API Webhook Handler
# =============================================================================

def _jid_local_part(jid: str) -> str:
    """Extract phone number from JID for Evolution."""
    if not jid:
        return ""
    base = jid.split("@")[0] if "@" in jid else jid
    # Strip WhatsApp device suffix (digits:user)
    if ":" in base and base.split(":")[0].isdigit():
        base = base.split(":")[0]
    return base


def _unwrap_proto_message(msg_block: dict) -> dict:
    """Follow common Baileys wrapper nodes (ephemeral, view-once) to the inner message dict."""
    if not isinstance(msg_block, dict):
        return {}
    cur: dict = msg_block
    for _ in range(4):
        wrapped = None
        for name in (
            "ephemeralMessage",
            "viewOnceMessage",
            "viewOnceMessageV2",
            "documentWithCaptionMessage",
        ):
            node = cur.get(name)
            if isinstance(node, dict) and isinstance(node.get("message"), dict):
                wrapped = node["message"]
                break
        if wrapped is None:
            break
        cur = wrapped
    return cur


def _extract_evolution_message_text(msg_block: dict) -> str:
    """Pull plaintext from Baileys message subtree."""
    if not isinstance(msg_block, dict):
        return ""
    base = _unwrap_proto_message(msg_block)
    inner = base.get("message") if isinstance(base.get("message"), dict) else {}
    parts = [
        base.get("conversation"),
        inner.get("conversation"),
        base.get("extendedTextMessage", {}).get("text"),
        inner.get("extendedTextMessage", {}).get("text"),
        base.get("imageMessage", {}).get("caption"),
        inner.get("imageMessage", {}).get("caption"),
        base.get("videoMessage", {}).get("caption"),
        base.get("documentMessage", {}).get("caption"),
    ]
    for p in parts:
        if isinstance(p, str) and p.strip():
            return p.strip()
    return ""


def parse_evolution_messages_payload(payload: dict) -> Optional[tuple[str, str, dict]]:
    """
    Parse Evolution API webhook payload.
    Returns (from_digits_or_key, message_text, key_dict) for inbound user messages.
    """
    data = payload.get("data")
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        data = {}

    # Batch upsert: data.messages[]
    msg_entries = data.get("messages")
    if isinstance(msg_entries, list) and msg_entries:
        data = msg_entries[0]
        if not isinstance(data, dict):
            data = {}

    msg_block = data.get("message") if isinstance(data.get("message"), dict) else {}
    key: dict = {}
    if isinstance(msg_block.get("key"), dict):
        key = msg_block["key"]
    if not key and isinstance(data.get("key"), dict):
        key = data["key"]
    if not key and isinstance(payload.get("key"), dict):
        key = payload["key"]

    if key.get("fromMe"):
        return None

    text = _extract_evolution_message_text(msg_block)

    raw_jid = key.get("remoteJid") or ""
    from_digits = _jid_local_part(raw_jid)

    # Official Evolution payload includes sender at root
    sender = payload.get("sender") or data.get("sender")
    if isinstance(sender, str) and sender.strip():
        digits = "".join(c for c in sender if c.isdigit())
        if digits:
            from_digits = digits

    if not text:
        return None

    if not from_digits:
        from_digits = "unknown"

    return (from_digits, text, key if isinstance(key, dict) else {})


# =============================================================================
# Tenant Resolution
# =============================================================================

async def resolve_webhook_tenant(request: Request, db: AsyncSession) -> Optional[Tenant]:
    """Resolve tenant from webhook request."""
    settings = get_settings()

    # Try query param first
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        t = result.scalar_one_or_none()
        if t:
            logger.info(f"Webhook resolved to tenant: {t.name} ({t.id})")
            return t

    # Fall back to configured tenant
    if settings.webhook_whatsapp_tenant_id:
        result = await db.execute(
            select(Tenant).where(Tenant.id == settings.webhook_whatsapp_tenant_id)
        )
        t = result.scalar_one_or_none()
        if t:
            return t

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
    """Process a WhatsApp message and generate response."""
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

    # Generate agent response
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
        return WebhookResponse(
            message="",
            success=False,
            agent_response=None,
            sources=None,
        )

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

    # Send via WhatsApp gateway
    await send_whatsapp_reply(tenant.id, from_number, result.answer, db)

    return WebhookResponse(
        message=result.answer,
        agent_response=result.answer,
        sources=result.sources,
        success=True,
    )


async def send_whatsapp_reply(tenant_id: str, to_number: str, message: str, db: AsyncSession):
    """Send WhatsApp reply via configured gateway."""
    try:
        import hashlib
        hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
        session_name = f"inika-{hash_suffix}"

        # Try Baileys Gateway first, then WAHA, then Evolution
        if settings.baileys_gateway_url:
            from app.services.baileys_client import BaileysGatewayClient
            client = BaileysGatewayClient(session_name=session_name)
            await client.send_message(to_number, message)
            await client.close()
            return

        if settings.waha_url:
            from app.services.waha_client import WAHAClient
            client = WAHAClient(session_name=session_name)
            await client.send_message(to_number, message)
            await client.close()
            return

        # Fall back to Evolution
        from app.services.evolution_client import EvolutionClient
        from app.services.whatsapp_service import WhatsAppService
        whatsapp_service = WhatsAppService(db)
        instance_name = whatsapp_service._get_tenant_instance_name(tenant_id)
        client = EvolutionClient(instance_name=instance_name)
        await client.send_message(to_number, message)
    except Exception:
        logger.exception("Failed to send WhatsApp reply")


# =============================================================================
# Baileys Gateway Webhook Endpoint
# =============================================================================

@router.post("/whatsapp-baileys", response_model=WebhookResponse)
async def receive_baileys_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive WhatsApp messages from Baileys Gateway.
    Baileys sends webhooks with event type and message data.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    logger.info(f"Baileys webhook received: {payload.get('event', 'unknown')}")

    # Parse Baileys message (same format as WAHA)
    parsed = parse_waha_message(payload)
    if not parsed:
        logger.info(f"Baileys webhook: no valid message parsed (event: {payload.get('event')})")
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    # Resolve tenant
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
# WAHA Webhook Endpoint
# =============================================================================

@router.post("/whatsapp-waha", response_model=WebhookResponse)
async def receive_waha_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive WhatsApp messages from WAHA gateway.
    WAHA sends webhooks with event type and message data.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    logger.info(f"WAHA webhook received: {payload.get('event', 'unknown')}")

    # Parse WAHA message
    parsed = parse_waha_message(payload)
    if not parsed:
        logger.info(f"WAHA webhook: no valid message parsed (event: {payload.get('event')})")
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    # Resolve tenant
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
# Evolution Webhook Endpoint (legacy)
# =============================================================================

@router.post("/whatsapp", response_model=WebhookResponse)
async def receive_evolution_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receive WhatsApp messages from Evolution API.
    Keep for backwards compatibility.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    logger.info(f"Evolution webhook received")

    parsed = parse_evolution_messages_payload(payload)
    if not parsed:
        logger.info("Evolution webhook: no valid message parsed")
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    tenant = await resolve_webhook_tenant(request, db)
    if not tenant:
        logger.warning("Webhook: no tenant for Evolution message")
        return WebhookResponse(message="No tenant configured", success=False)

    return await handle_whatsapp_message(
        tenant=tenant,
        from_number=from_number,
        message_content=message_content,
        msg_id=msg_id,
        db=db,
    )


@router.post("/whatsapp/messages-upsert", response_model=WebhookResponse)
async def receive_evolution_messages_upsert(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Same handler for Evolution's messages-upsert endpoint."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    parsed = parse_evolution_messages_payload(payload)
    if not parsed:
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    tenant = await resolve_webhook_tenant(request, db)
    if not tenant:
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
async def get_status(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get WhatsApp and Agent status for a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

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