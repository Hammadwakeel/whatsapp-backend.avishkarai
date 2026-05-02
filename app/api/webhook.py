"""Webhook API Routes - For Evolution API and external integrations"""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4

from app.core import get_db
from app.models import Tenant
from app.services.whatsapp_service import WhatsAppService
from app.services.agent_service import AgentService
from app.schemas.whatsapp import WhatsAppMessageCreate
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_tenant_from_session(session_id: str, db: AsyncSession) -> Optional[Tenant]:
    """Find tenant by session_id or tenant_id"""
    from sqlalchemy import select

    # Try to extract tenant_id from session_id (format: tenant_<tenant_id>)
    if session_id.startswith("tenant_"):
        tenant_id = session_id.replace("tenant_", "")
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    # Otherwise, look up by ID
    result = await db.execute(select(Tenant).where(Tenant.id == session_id))
    return result.scalar_one_or_none()


@router.post("/whatsapp", response_model=WebhookResponse)
async def receive_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Receive WhatsApp message from Evolution API and generate AI response"""

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Extract message data from Evolution API format
    data = payload.get("data", {})
    message_info = data.get("message", {})
    key = message_info.get("key", {})

    # Skip outgoing messages (from us)
    if key.get("fromMe", False):
        return WebhookResponse(message="", success=True)

    # Extract sender and message
    from_number = key.get("remoteJid", "").split("@")[0] if "@" in key.get("remoteJid", "") else key.get("remoteJid", "")
    message_content = message_info.get("conversation") or message_info.get("extendedTextMessage", {}).get("text", "")

    if not message_content:
        return WebhookResponse(message="", success=True)

    # Find tenant (use default tenant for now - implement routing logic as needed)
    from sqlalchemy import select
    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()

    if not tenant:
        return WebhookResponse(message="No tenant configured", success=False)

    # Record inbound message
    whatsapp_service = WhatsAppService(db)
    message_data = WhatsAppMessageCreate(
        session_id=tenant.id,
        message_id=key.get("id"),
        direction="inbound",
        from_number=from_number,
        content=message_content,
    )
    await whatsapp_service.record_message(tenant.id, message_data)

    # Generate AI response using agent service
    agent_service = AgentService(db)
    from app.schemas.agent import AgentTestRequest

    test_request = AgentTestRequest(
        question=message_content,
        context=f"WhatsApp message from {from_number}"
    )

    result = await agent_service.test_agent(tenant.id, test_request)

    # Record outbound response
    response_data = WhatsAppMessageCreate(
        session_id=tenant.id,
        message_id=str(uuid4()),
        direction="outbound",
        from_number="",
        to_number=from_number,
        content=result.answer,
        agent_response=result.answer,
        wiki_sources={"sources": result.sources} if result.sources else None,
        web_search_used=result.web_search_used,
    )
    await whatsapp_service.record_message(tenant.id, response_data)

    # Send response via Evolution API
    from app.services.evolution_client import evolution_client
    await evolution_client.send_message(from_number, result.answer)

    return WebhookResponse(
        message=result.answer,
        agent_response=result.answer,
        sources=result.sources,
        success=True
    )


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    return {"status": "healthy", "service": "inika-webhook"}


@router.post("/agent", response_model=WebhookResponse)
async def agent_query(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Agent query endpoint for external integrations"""

    # Extract parameters
    tenant_id = request.get("tenant_id")
    query = request.get("query")
    session_id = request.get("session_id")

    if not tenant_id or not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing tenant_id or query"
        )

    # Verify tenant exists
    from sqlalchemy import select
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    # Process query
    agent_service = AgentService(db)
    from app.schemas.agent import AgentTestRequest

    test_request = AgentTestRequest(
        question=query,
        context=f"Agent query from session {session_id}"
    )

    result = await agent_service.test_agent(tenant_id, test_request)

    return WebhookResponse(
        message=result.answer,
        agent_response=result.answer,
        sources=result.sources,
        success=True
    )


@router.get("/status/{tenant_id}")
async def get_status(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get WhatsApp and Agent status for a tenant"""

    from sqlalchemy import select
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
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
        }
    }