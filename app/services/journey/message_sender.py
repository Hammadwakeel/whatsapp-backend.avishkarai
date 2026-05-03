"""Message Sender - Send journey messages via WhatsApp"""

from __future__ import annotations

import hashlib
from typing import Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.baileys_client import BaileysGatewayClient
from app.models.journey import JourneyMessageLog, JourneyConversation, JourneyMessage


class JourneyMessageSender:
    """Send journey messages via WhatsApp Baileys Gateway."""

    def __init__(self, db: AsyncSession = None):
        self.db = db

    async def send_journey_message(
        self,
        tenant_id: str,
        guest: dict,
        message: str,
        message_type: str,
        weather: dict = None,
        wiki_context: dict = None,
    ) -> dict[str, Any]:
        """
        Send a journey message to a guest via WhatsApp.

        Args:
            tenant_id: Tenant ID
            guest: Guest data from booking
            message: Message content
            message_type: Type of message
            weather: Weather context used
            wiki_context: Wiki sources used

        Returns:
            Dict with send status and message details
        """
        guest_mobile = guest.get("mobile")
        if not guest_mobile:
            return {
                "status": "error",
                "error": "Guest has no mobile number"
            }

        # Format phone number for WhatsApp
        phone = self._format_phone(guest_mobile)

        try:
            # Send via Baileys Gateway
            hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
            session_name = f"inika-{hash_suffix}"
            client = BaileysGatewayClient(session_name=session_name)
            result = await client.send_message(phone=phone, message=message)
            await client.close()

            if result.get("success"):
                # Log the message
                if self.db:
                    log = JourneyMessageLog(
                        id=str(uuid4()),
                        tenant_id=tenant_id,
                        guest_id=guest.get("id"),
                        guest_name=guest.get("gname"),
                        guest_mobile=guest_mobile,
                        room_number=guest.get("room"),
                        message_type=message_type,
                        direction="outbound",
                        content=message,
                        weather=weather,
                        guest_status=guest.get("gstatus"),
                        sent_at=datetime.utcnow(),
                        delivered=True,
                        ai_generated=True,
                        wiki_context=wiki_context,
                    )
                    self.db.add(log)
                    await self.db.commit()

                return {
                    "status": "ok",
                    "message_id": result.get("message_id"),
                    "sent_to": phone,
                    "message_type": message_type,
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to send")
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def send_batch_messages(
        self,
        tenant_id: str,
        guests: list[dict],
        message: str,
        message_type: str,
        weather: dict = None,
    ) -> dict[str, Any]:
        """Send the same message to multiple guests."""
        results = []
        success_count = 0
        failed_count = 0

        for guest in guests:
            result = await self.send_journey_message(
                tenant_id=tenant_id,
                guest=guest,
                message=message,
                message_type=message_type,
                weather=weather,
            )

            if result.get("status") == "ok":
                success_count += 1
            else:
                failed_count += 1

            results.append({
                "guest_id": guest.get("id"),
                "guest_name": guest.get("gname"),
                "status": result.get("status"),
                "error": result.get("error"),
            })

        return {
            "status": "completed",
            "total": len(guests),
            "success": success_count,
            "failed": failed_count,
            "results": results,
        }

    async def log_inbound_message(
        self,
        tenant_id: str,
        conversation_id: str,
        content: str,
        guest: dict = None,
    ) -> JourneyMessage:
        """Log an incoming message from guest."""
        if not self.db:
            return None

        message = JourneyMessage(
            id=str(uuid4()),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            direction="inbound",
            content=content,
            sent_at=datetime.utcnow(),
            ai_generated=False,
        )
        self.db.add(message)
        await self.db.commit()
        return message

    async def log_outbound_message(
        self,
        tenant_id: str,
        conversation_id: str,
        content: str,
        response: str = None,
        wiki_sources: list = None,
        web_search_used: bool = False,
    ) -> JourneyMessage:
        """Log an outbound AI response."""
        if not self.db:
            return None

        message = JourneyMessage(
            id=str(uuid4()),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            direction="outbound",
            content=content,
            agent_response=response,
            wiki_sources=wiki_sources,
            web_search_used=web_search_used,
            sent_at=datetime.utcnow(),
            ai_generated=True,
        )
        self.db.add(message)
        await self.db.commit()
        return message

    async def get_or_create_conversation(
        self,
        tenant_id: str,
        guest_mobile: str,
        guest: dict = None,
    ) -> str:
        """Get or create a conversation thread for a guest."""
        if not self.db:
            return str(uuid4())

        from sqlalchemy import select
        from app.models.journey import JourneyConversation

        # Check if conversation exists
        result = await self.db.execute(
            select(JourneyConversation).where(
                JourneyConversation.guest_mobile == guest_mobile,
                JourneyConversation.tenant_id == tenant_id
            )
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            # Update last message time
            conversation.last_message_at = datetime.utcnow()
            conversation.message_count += 1

            # Update guest info if changed
            if guest and guest.get("gname"):
                conversation.guest_name = guest.get("gname")
            if guest and guest.get("room"):
                conversation.room_number = guest.get("room")

            await self.db.commit()
            return conversation.id

        # Create new conversation
        conversation = JourneyConversation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            guest_id=guest.get("id") if guest else None,
            guest_name=guest.get("gname") if guest else None,
            guest_mobile=guest_mobile,
            room_number=guest.get("room") if guest else None,
            last_message_at=datetime.utcnow(),
            message_count=1,
            is_active=True,
        )
        self.db.add(conversation)
        await self.db.commit()
        return conversation.id

    def _format_phone(self, phone: str) -> str:
        """Format phone number for WhatsApp."""
        # Remove any spaces or special characters
        phone = phone.strip().replace(" ", "").replace("-", "").replace("+", "")

        # If it doesn't start with country code, assume local
        if len(phone) <= 10:
            return f"92{phone}"  # Assume Pakistan if 10 digits

        return phone


async def send_journey_message(
    tenant_id: str,
    guest: dict,
    message: str,
    message_type: str,
    weather: dict = None,
) -> dict[str, Any]:
    """Convenience function to send a journey message."""
    sender = JourneyMessageSender()
    return await sender.send_journey_message(
        tenant_id, guest, message, message_type, weather
    )


async def send_batch_journey_messages(
    tenant_id: str,
    guests: list[dict],
    message: str,
    message_type: str,
    weather: dict = None,
) -> dict[str, Any]:
    """Convenience function to send batch messages."""
    sender = JourneyMessageSender()
    return await sender.send_batch_messages(
        tenant_id, guests, message, message_type, weather
    )