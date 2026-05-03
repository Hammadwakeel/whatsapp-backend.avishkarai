"""WhatsApp Service - Manages WhatsApp sessions and messages"""

import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, TYPE_CHECKING

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WhatsAppSession, WhatsAppMessage, SessionStatus
from app.schemas.whatsapp import (
    WhatsAppSessionUpdate, WhatsAppSessionResponse,
    WhatsAppStatusResponse, QRCodeResponse,
    WhatsAppMessageCreate, WhatsAppMessageResponse,
)

if TYPE_CHECKING:
    from app.services.sse_manager import SSEManager


class WhatsAppService:
    """Service for managing WhatsApp sessions and messages"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_tenant_session_name(self, tenant_id: str) -> str:
        """Generate a tenant-specific session name for the WhatsApp gateway.

        Uses a hash of tenant_id to create a unique but stable session name.
        Format: inika-{8char_hash}
        """
        hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
        return f"inika-{hash_suffix}"

    async def get_or_create_session(self, tenant_id: str) -> WhatsAppSession:
        """Get existing session or create a new one for tenant with tenant-specific instance name."""
        result = await self.db.execute(
            select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            session_name = self._get_tenant_session_name(tenant_id)
            session = WhatsAppSession(
                id=str(uuid4()),
                tenant_id=tenant_id,
                status=SessionStatus.DISCONNECTED.value,
                gateway_session_name=session_name,
            )
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)

        return session

    async def get_session(self, tenant_id: str) -> Optional[WhatsAppSession]:
        """Get WhatsApp session for tenant"""
        result = await self.db.execute(
            select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def update_session(
        self,
        tenant_id: str,
        update_data: WhatsAppSessionUpdate
    ) -> WhatsAppSession:
        """Update WhatsApp session"""
        session = await self.get_or_create_session(tenant_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(session, field):
                setattr(session, field, value)

        session.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_status(
        self,
        tenant_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> WhatsAppSession:
        """Update session status"""
        session = await self.get_or_create_session(tenant_id)
        session.status = status
        if error_message:
            session.error_message = error_message
        if status == SessionStatus.CONNECTED.value:
            session.connected_at = datetime.now(timezone.utc)
            session.qr_code = None
            session.qr_expires_at = None
        session.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def set_qr_code(
        self,
        tenant_id: str,
        qr_code: str,
        expires_at: datetime
    ) -> WhatsAppSession:
        """Set QR code for session"""
        session = await self.get_or_create_session(tenant_id)
        session.qr_code = qr_code
        session.qr_expires_at = expires_at
        session.status = SessionStatus.CONNECTING.value
        session.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_status(self, tenant_id: str) -> WhatsAppStatusResponse:
        """Get WhatsApp connection status"""
        session = await self.get_session(tenant_id)
        message_count = await self.get_message_count(tenant_id)

        if not session:
            return WhatsAppStatusResponse(
                is_connected=False,
                status=SessionStatus.DISCONNECTED.value,
                phone_number=None,
                display_name=None,
                connected_at=None,
                last_activity=None,
                message_count=message_count,
            )

        return WhatsAppStatusResponse(
            is_connected=session.status == SessionStatus.CONNECTED.value,
            status=session.status,
            qrcode=session.qr_code,
            phone_number=session.phone_number,
            display_name=session.display_name,
            connected_at=session.connected_at,
            last_activity=session.last_activity,
            message_count=message_count,
            local_session_id=session.id,
        )

    async def get_qr_code(self, tenant_id: str) -> Optional[QRCodeResponse]:
        """Get current QR code if available"""
        session = await self.get_session(tenant_id)
        if session and session.qr_code and session.qr_expires_at:
            return QRCodeResponse(
                qr_code=session.qr_code,
                expires_at=session.qr_expires_at
            )
        return None

    async def record_message(
        self,
        tenant_id: str,
        message_data: WhatsAppMessageCreate,
        broadcast: bool = True,
        sse_manager: Optional["SSEManager"] = None,
    ) -> WhatsAppMessage:
        """Record a message in the database"""
        session = await self.get_session(tenant_id)

        message = WhatsAppMessage(
            id=str(uuid4()),
            tenant_id=tenant_id,
            session_id=session.id if session else None,
            message_id=message_data.message_id,
            direction=message_data.direction,
            from_number=message_data.from_number,
            to_number=message_data.to_number,
            content=message_data.content,
            agent_response=message_data.agent_response,
            wiki_sources=message_data.wiki_sources,
            web_search_used=message_data.web_search_used,
            response_time_ms=message_data.response_time_ms,
            is_delivered=True,
        )
        self.db.add(message)

        # Update session last_activity
        if session:
            session.last_activity = datetime.now(timezone.utc)
            await self.db.commit()
        else:
            await self.db.commit()

        await self.db.refresh(message)

        # Broadcast new message via SSE if enabled
        if broadcast and sse_manager:
            from app.services.sse_manager import sse_manager as global_sse_manager
            msg_dict = WhatsAppMessageResponse.model_validate(message).model_dump(mode="json")
            await global_sse_manager.broadcast_new_message(tenant_id, msg_dict)

        return message

    async def get_messages(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        direction: Optional[str] = None,
        order: str = "desc",
    ) -> tuple[list[WhatsAppMessage], int]:
        """Get messages for tenant with pagination"""
        # Build base query
        query = select(WhatsAppMessage).where(WhatsAppMessage.tenant_id == tenant_id)
        count_query = select(func.count(WhatsAppMessage.id)).where(WhatsAppMessage.tenant_id == tenant_id)

        if direction:
            query = query.where(WhatsAppMessage.direction == direction)
            count_query = count_query.where(WhatsAppMessage.direction == direction)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated messages
        offset = (page - 1) * page_size
        ord_col = (
            WhatsAppMessage.created_at.asc()
            if order == "asc"
            else WhatsAppMessage.created_at.desc()
        )
        query = query.order_by(ord_col).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        return messages, total

    async def get_message_count(self, tenant_id: str) -> int:
        """Get total message count for tenant"""
        result = await self.db.execute(
            select(func.count(WhatsAppMessage.id)).where(WhatsAppMessage.tenant_id == tenant_id)
        )
        return result.scalar() or 0

    async def mark_delivered(self, message_id: str) -> bool:
        """Mark a message as delivered"""
        result = await self.db.execute(
            select(WhatsAppMessage).where(WhatsAppMessage.id == message_id)
        )
        message = result.scalar_one_or_none()
        if message:
            message.is_delivered = True
            await self.db.commit()
            return True
        return False