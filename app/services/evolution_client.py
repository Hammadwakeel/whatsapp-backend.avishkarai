"""Evolution API Client - Manages WhatsApp sessions via Evolution API"""

import httpx
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EvolutionClient:
    """Client for Evolution API - Free WhatsApp Gateway"""

    def __init__(self):
        self.base_url = settings.evolution_url.rstrip("/")
        self.api_key = settings.evolution_api_key
        self.instance_name = settings.evolution_instance_name
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
                headers={
                    "apikey": self.api_key,
                    "Content-Type": "application/json"
                }
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> dict:
        """Check Evolution API health"""
        try:
            client = await self._get_client()
            response = await client.get(f"/instance/connectionState/{self.instance_name}")
            if response.status_code == 200:
                data = response.json()
                return {
                    "ok": True,
                    "instance": self.instance_name,
                    "status": data.get("instance", {}).get("status", "unknown")
                }
            return {"ok": False, "error": f"Status: {response.status_code}"}
        except Exception as e:
            logger.error(f"Evolution health check failed: {e}")
            return {"ok": False, "error": str(e)}

    async def get_connection_status(self) -> dict:
        """Get WhatsApp connection status"""
        try:
            client = await self._get_client()
            response = await client.get(f"/instance/connectionState/{self.instance_name}")

            if response.status_code == 200:
                data = response.json()
                state = data.get("state", "DISCONNECTED")

                return {
                    "connected": state == "CONNECTED",
                    "status": state,
                    "qr_code": data.get("qrCode"),
                    "message": self._get_status_message(state)
                }
            return {"connected": False, "status": "ERROR", "message": "Failed to get status"}
        except Exception as e:
            logger.error(f"Failed to get connection status: {e}")
            return {"connected": False, "status": "ERROR", "message": str(e)}

    def _get_status_message(self, state: str) -> str:
        """Get human-readable status message"""
        messages = {
            "CONNECTED": "WhatsApp is connected and ready",
            "DISCONNECTED": "WhatsApp is disconnected",
            "CONNECTING": "WhatsApp is connecting...",
            "DISCONNECTING": "WhatsApp is disconnecting...",
            "QRCODE": "Waiting for QR scan",
            "DISCONNECTED_BY_OWNER": "Disconnected by owner"
        }
        return messages.get(state, f"Status: {state}")

    async def generate_qr_code(self) -> dict:
        """Generate QR code for WhatsApp pairing"""
        try:
            client = await self._get_client()

            # First check current status
            status = await self.get_connection_status()

            if status.get("connected"):
                return {
                    "success": True,
                    "qr_code": None,
                    "already_connected": True,
                    "message": "WhatsApp is already connected"
                }

            # Check if QR is already available
            if status.get("qr_code"):
                return {
                    "success": True,
                    "qr_code": status["qr_code"],
                    "message": "QR code available"
                }

            # Request new QR code
            response = await client.post(
                "/instance/connect",
                json={"instanceName": self.instance_name}
            )

            if response.status_code == 200:
                data = response.json()
                qr_code = data.get("qrCode", {})

                return {
                    "success": True,
                    "qr_code": qr_code,
                    "message": "QR code generated"
                }

            return {
                "success": False,
                "error": f"Failed to generate QR: {response.status_code}",
                "details": response.text
            }

        except Exception as e:
            logger.error(f"Failed to generate QR: {e}")
            return {"success": False, "error": str(e)}

    async def get_qr_code_image(self) -> Optional[str]:
        """Get QR code as base64 image"""
        try:
            client = await self._get_client()
            response = await client.get(f"/instance/qrCode/{self.instance_name}")

            if response.status_code == 200:
                data = response.json()
                return data.get("qrcode")
            return None
        except Exception as e:
            logger.error(f"Failed to get QR image: {e}")
            return None

    async def logout(self) -> dict:
        """Disconnect WhatsApp"""
        try:
            client = await self._get_client()
            response = await client.delete(f"/instance/logout/{self.instance_name}")

            return {
                "success": response.status_code in [200, 204],
                "message": "Logged out successfully" if response.status_code in [200, 204] else "Logout failed"
            }
        except Exception as e:
            logger.error(f"Failed to logout: {e}")
            return {"success": False, "error": str(e)}

    async def send_message(self, phone: str, message: str) -> dict:
        """Send a text message"""
        try:
            client = await self._get_client()

            # Format phone number (ensure it has country code)
            phone = self._format_phone(phone)

            payload = {
                "number": phone,
                "text": message
            }

            response = await client.post(
                "/message/sendText",
                params={"instanceName": self.instance_name},
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "message_id": data.get("key", {}).get("id"),
                    "message": "Message sent successfully"
                }

            return {
                "success": False,
                "error": f"Failed to send: {response.status_code}",
                "details": response.text
            }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {"success": False, "error": str(e)}

    def _format_phone(self, phone: str) -> str:
        """Format phone number to WhatsApp format"""
        phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

        # Add @s.whatsapp.net if not present
        if "@s.whatsapp.net" not in phone and "@g.us" not in phone:
            if phone.startswith("92"):
                phone = phone + "@s.whatsapp.net"
            elif phone.startswith("+"):
                phone = phone[1:] + "@s.whatsapp.net"
            elif not phone.endswith("@s.whatsapp.net"):
                phone = phone + "@s.whatsapp.net"

        return phone

    async def receive_webhook(self, payload: dict) -> dict:
        """Process incoming webhook from Evolution API"""
        try:
            # Extract message info
            message_data = payload.get("data", {}).get("message", {})
            key = message_data.get("key", {})

            # Only process incoming messages (not sent by us)
            if key.get("fromMe", False):
                return {"processed": False, "reason": "outgoing message"}

            remote_jid = key.get("remoteJid", "")
            message_text = message_data.get("conversation") or message_data.get("extendedTextMessage", {}).get("text", "")

            return {
                "processed": True,
                "from": remote_jid.split("@")[0] if "@" in remote_jid else remote_jid,
                "message": message_text,
                "message_id": key.get("id"),
                "timestamp": message_data.get("messageTimestamp"),
                "push_name": payload.get("data", {}).get("pushName", "Unknown")
            }

        except Exception as e:
            logger.error(f"Failed to process webhook: {e}")
            return {"processed": False, "error": str(e)}


# Global client instance
evolution_client = EvolutionClient()