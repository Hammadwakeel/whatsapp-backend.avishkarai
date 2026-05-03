"""Webhook API Routes - For Evolution API and external integrations"""

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


class WebhookMessageRequest(BaseModel):
    """Incoming message format from Evolution API"""

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


def _jid_local_part(jid: str) -> str:
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


def _extract_message_text(msg_block: dict) -> str:
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
    Returns (from_digits_or_key, message_text, key_dict) for inbound user messages.
    Evolution sends event 'messages.upsert' with shapes:
      - data.key + data.message.{conversation|...}
      - data.messages[] entries
    Root may include 'sender' (phone digits).
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

    # Key may be on `data` (Baileys) or inside `data.message` (Evolution / WEBHOOK.md shape).
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

    text = _extract_message_text(msg_block)

    raw_jid = key.get("remoteJid") or ""
    from_digits = _jid_local_part(raw_jid)

    # Official Evolution payload includes sender at root (E.164-ish digits)
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


async def resolve_webhook_tenant(request: Request, db: AsyncSession) -> Optional[Tenant]:
    settings = get_settings()
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        t = result.scalar_one_or_none()
        if t:
            return t

    if settings.webhook_whatsapp_tenant_id:
        result = await db.execute(
            select(Tenant).where(Tenant.id == settings.webhook_whatsapp_tenant_id)
        )
        t = result.scalar_one_or_none()
        if t:
            return t

    result = await db.execute(select(Tenant).limit(1))
    return result.scalar_one_or_none()


async def handle_evolution_whatsapp_webhook(
    request: Request,
    db: AsyncSession,
    payload: dict[str, Any],
) -> WebhookResponse:
    parsed = parse_evolution_messages_payload(payload)
    if not parsed:
        return WebhookResponse(message="", success=True)

    from_number, message_content, key = parsed
    msg_id = key.get("id") if isinstance(key, dict) else None

    tenant = await resolve_webhook_tenant(request, db)
    if not tenant:
        logger.warning("Webhook: no tenant for inbound WhatsApp message")
        return WebhookResponse(message="No tenant configured", success=False)

    whatsapp_service = WhatsAppService(db)

    # Get tenant-specific evolution client for sending reply
    from app.api.whatsapp import get_tenant_evolution_client
    evolution_client = get_tenant_evolution_client(whatsapp_service, tenant.id)

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

    try:
        send_result = await evolution_client.send_message(from_number, result.answer)
        if not send_result.get("success"):
            logger.warning(
                "Evolution send_message failed: %s",
                send_result.get("error") or send_result,
            )
    except Exception:
        logger.exception("Evolution send_message raised")

    return WebhookResponse(
        message=result.answer,
        agent_response=result.answer,
        sources=result.sources,
        success=True,
    )


@router.post("/whatsapp", response_model=WebhookResponse)
async def receive_whatsapp_message(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive WhatsApp messages from Evolution (global or instance webhook URL)."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    return await handle_evolution_whatsapp_webhook(request, db, payload)


@router.post("/whatsapp/messages-upsert", response_model=WebhookResponse)
async def receive_whatsapp_messages_upsert(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Same handler when Evolution uses WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true
    (posts to …/messages-upsert).
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

    return await handle_evolution_whatsapp_webhook(request, db, payload)


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    return {"status": "healthy", "service": "inika-webhook"}


@router.get("/status/{tenant_id}")
async def get_status(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """Get WhatsApp and Agent status for a tenant"""
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
