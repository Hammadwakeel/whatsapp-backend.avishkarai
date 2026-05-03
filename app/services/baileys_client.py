"""Baileys Gateway Client - Multi-tenant WhatsApp via local Baileys gateway"""

import asyncio
import logging
from typing import Optional, Any
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class BaileysGatewayClient:
    """Client for the Inika Baileys-based WhatsApp gateway.

    This gateway runs locally and manages multiple WhatsApp sessions
    for different tenants using the Baileys library.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        session_name: str = "default"
    ):
        """
        Create Baileys Gateway client.

        Args:
            base_url: Gateway server URL (default from settings)
            api_key: API key (if configured)
            session_name: Session name for this tenant
        """
        settings = get_settings()
        self.base_url = (base_url or settings.baileys_gateway_url or "http://localhost:3002").rstrip("/")
        self.api_key = api_key or settings.baileys_gateway_api_key or ""
        self.session_name = session_name
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["x-api-key"] = self.api_key
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
                headers=headers
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> dict:
        """Check Baileys Gateway health"""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            if response.status_code == 200:
                return {"ok": True, "status": "healthy"}
            return {"ok": False, "error": f"Status: {response.status_code}"}
        except Exception as e:
            logger.error(f"Baileys Gateway health check failed: {e}")
            return {"ok": False, "error": str(e)}

    def _state_from_status(self, status: str) -> str:
        """Convert gateway status to standard status"""
        status = (status or "").upper()
        status_map = {
            "CONNECTING": "CONNECTING",
            "CONNECTED": "CONNECTED",
            "AUTHENTICATED": "CONNECTED",
            "LOGGED_IN": "CONNECTED",
            "SCANNING": "CONNECTING",
            "DISCONNECTED": "DISCONNECTED",
            "CLOSED": "DISCONNECTED",
            "LOGOUT": "DISCONNECTED",
        }
        return status_map.get(status, status)

    async def get_connection_status(self) -> dict:
        """Get WhatsApp connection status from Baileys Gateway"""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/sessions/{self.session_name}")

            if response.status_code == 200:
                data = response.json()
                gateway_status = data.get("status", "UNKNOWN")
                status = self._state_from_status(gateway_status)
                is_connected = status == "CONNECTED"

                return {
                    "connected": is_connected,
                    "status": status,
                    "phone_number": data.get("number"),
                    "display_name": data.get("pushName") or data.get("name"),
                    "qr_code": None,  # QR is only available when not authenticated
                    "session": data,
                }

            if response.status_code == 404:
                return {
                    "connected": False,
                    "status": "DISCONNECTED",
                    "message": "Session not found - need to create and start",
                }

            return {
                "connected": False,
                "status": "ERROR",
                "message": f"Status: {response.status_code}",
            }
        except Exception as e:
            logger.error(f"Failed to get Baileys Gateway connection status: {e}")
            return {"connected": False, "status": "ERROR", "message": str(e)}

    async def create_session(self, webhook_url: Optional[str] = None, force: bool = False) -> dict:
        """Create a new Baileys session"""
        try:
            client = await self._get_client()

            payload = {
                "name": self.session_name,
                "config": {
                    "webhookUrl": webhook_url,
                    "webhookEvents": ["onMessage", "onStatus", "onQr"],
                }
            }

            if force:
                payload["force"] = True

            response = await client.post("/api/sessions", json=payload)

            if response.status_code in (200, 201):
                return {"success": True, "session": response.json()}

            # Session might already exist
            if response.status_code == 409:
                return {"success": True, "exists": True, "message": "Session already exists"}

            return {
                "success": False,
                "error": f"Failed to create session: {response.status_code}",
                "details": response.text,
            }
        except Exception as e:
            logger.error(f"Failed to create Baileys session: {e}")
            return {"success": False, "error": str(e)}

    async def start_session(self) -> dict:
        """Start/resume a Baileys session"""
        try:
            client = await self._get_client()
            response = await client.post(f"/api/sessions/{self.session_name}/start")

            if response.status_code in (200, 201):
                return {"success": True}

            # Already started
            if response.status_code == 409:
                return {"success": True, "already_started": True}

            return {
                "success": False,
                "error": f"Failed to start session: {response.status_code}",
            }
        except Exception as e:
            logger.error(f"Failed to start Baileys session: {e}")
            return {"success": False, "error": str(e)}

    async def generate_qr_code(self, webhook_url: Optional[str] = None, force: bool = False) -> dict:
        """Generate QR code for WhatsApp pairing via Baileys Gateway"""
        try:
            # First ensure session exists
            await self.create_session(webhook_url=webhook_url, force=force)

            # Poll for QR code - the gateway keeps retrying WhatsApp connection
            # so the QR may appear after a few seconds
            client = await self._get_client()
            max_attempts = 20
            poll_interval = 3  # seconds between each poll (20 * 3 = 60s total wait)

            for attempt in range(max_attempts):
                await asyncio.sleep(poll_interval)

                response = await client.get(f"/api/sessions/{self.session_name}/qr")

                if response.status_code == 200:
                    data = response.json()
                    qr_data = data.get("qr", [])

                    if qr_data and len(qr_data) > 0:
                        qr_item = qr_data[0]
                        base64_qr = qr_item.get("base64", "")

                        if base64_qr:
                            # Convert to data URL if needed
                            if not base64_qr.startswith("data:"):
                                base64_qr = f"data:image/png;base64,{base64_qr}"

                            return {
                                "success": True,
                                "qr_code": base64_qr,
                                "message": "QR code generated",
                            }

                # Check if already connected
                status = await self.get_connection_status()
                if status.get("connected"):
                    return {
                        "success": True,
                        "qr_code": None,
                        "already_connected": True,
                        "message": "WhatsApp is already connected",
                    }

            # Final check after all attempts
            status = await self.get_connection_status()
            if status.get("connected"):
                return {
                    "success": True,
                    "qr_code": None,
                    "already_connected": True,
                    "message": "WhatsApp is already connected",
                }

            return {
                "success": False,
                "error": "No QR code available after retries",
                "details": "WhatsApp connection may be blocked. Try a different network or VPN.",
            }
        except Exception as e:
            logger.error(f"Failed to generate Baileys QR: {e}")
            return {"success": False, "error": str(e)}

    async def get_qr_code_image(self) -> Optional[str]:
        """Get current QR code as base64 image"""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/sessions/{self.session_name}/qr")

            if response.status_code == 200:
                data = response.json()
                qr_data = data.get("qr", [])

                if qr_data and len(qr_data) > 0:
                    qr_item = qr_data[0]
                    base64_qr = qr_item.get("base64", "")
                    if base64_qr:
                        if not base64_qr.startswith("data:"):
                            base64_qr = f"data:image/png;base64,{base64_qr}"
                        return base64_qr
            return None
        except Exception as e:
            logger.error(f"Failed to get Baileys QR image: {e}")
            return None

    async def logout(self) -> dict:
        """Disconnect WhatsApp session"""
        try:
            client = await self._get_client()
            response = await client.delete(f"/api/sessions/{self.session_name}")

            if response.status_code in (200, 204):
                return {"success": True, "message": "Logged out successfully"}

            return {
                "success": False,
                "error": f"Logout failed: {response.status_code}",
            }
        except Exception as e:
            logger.error(f"Failed to logout: {e}")
            return {"success": False, "error": str(e)}

    async def send_message(self, phone: str, message: str) -> dict:
        """Send a text message via Baileys Gateway"""
        try:
            client = await self._get_client()

            # Format phone number
            phone = self._format_phone(phone)

            payload = {
                "session": self.session_name,
                "chatId": phone,
                "text": message,
            }

            response = await client.post("/api/messages/sendText", json=payload)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message_id": data.get("key", {}).get("id"),
                    "message": "Message sent successfully",
                }

            return {
                "success": False,
                "error": f"Failed to send: {response.status_code}",
                "details": response.text,
            }
        except Exception as e:
            logger.error(f"Failed to send message via Baileys: {e}")
            return {"success": False, "error": str(e)}

    def _format_phone(self, phone: str) -> str:
        """Format phone number to WhatsApp format"""
        phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # Ensure country code format
        if "@s.whatsapp.net" not in phone and "@g.us" not in phone:
            if phone.startswith("92"):
                phone = phone + "@s.whatsapp.net"
            elif phone.startswith("+"):
                phone = phone[1:] + "@s.whatsapp.net"
            elif not phone.endswith("@s.whatsapp.net"):
                phone = phone + "@s.whatsapp.net"

        return phone

    async def get_me(self) -> Optional[dict]:
        """Get info about the logged-in WhatsApp account"""
        try:
            client = await self._get_client()
            response = await client.get(f"/api/sessions/{self.session_name}")

            if response.status_code == 200:
                data = response.json()
                return {
                    "phone": data.get("number"),
                    "name": data.get("pushName") or data.get("name"),
                    "img_url": data.get("imgUrl"),
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get Baileys me info: {e}")
            return None


# Convenience function to create client for a tenant
def create_baileys_client(tenant_id: str) -> BaileysGatewayClient:
    """Create a Baileys Gateway client for a specific tenant."""
    import hashlib
    hash_suffix = hashlib.md5(tenant_id.encode()).hexdigest()[:8]
    session_name = f"inika-{hash_suffix}"
    return BaileysGatewayClient(session_name=session_name)