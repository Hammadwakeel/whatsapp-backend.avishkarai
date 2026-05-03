"""Evolution API Client - Manages WhatsApp sessions via Evolution API"""

import asyncio
import base64
import logging
from typing import Any, Optional

import httpx
from datetime import datetime

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EvolutionClient:
    """Client for Evolution API - Free WhatsApp Gateway"""

    def __init__(self, instance_name: Optional[str] = None):
        """
        Create an EvolutionClient instance.

        Args:
            instance_name: Tenant-specific instance name. If None, uses config default.
                          For per-tenant isolation, pass tenant-specific name like f"inika-{tenant_id[:8]}"
        """
        self.base_url = settings.evolution_url.rstrip("/")
        self.api_key = settings.evolution_api_key
        self.instance_name = instance_name or settings.evolution_instance_name
        self._client: Optional[httpx.AsyncClient] = None
        self._qr_diag: dict[str, Any] = {}
        self._last_pairing_code: Optional[str] = None
        self._last_known_state: Optional[str] = None  # Track state changes

    def evolution_user_hint(self) -> Optional[str]:
        """Short message for API/UI when QR cannot be loaded."""
        if self._qr_diag.get("error"):
            return str(self._qr_diag["error"])
        if self._qr_diag.get("create_error"):
            return f"Evolution create instance: {str(self._qr_diag['create_error'])[:220]}"
        if self._qr_diag.get("connect_error"):
            return str(self._qr_diag["connect_error"])[:220]
        if self._qr_diag.get("connectionState_error"):
            return f"connectionState: {str(self._qr_diag['connectionState_error'])[:180]}"
        ch = self._qr_diag.get("create_http")
        cs = self._qr_diag.get("connectionState_http")
        if ch and ch not in (200, 201):
            return f"HTTP create instance returned {ch}"
        if cs and cs not in (200, 404):
            return f"Evolution HTTP {cs} — check EVOLUTION_URL and apikey"
        return None

    def get_pairing_code(self) -> Optional[str]:
        return self._last_pairing_code

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

    def _extract_instance_state(self, data: dict) -> str:
        """Evolution v1 uses top-level state; v2 nests under instance.state."""
        inst = data.get("instance")
        if isinstance(inst, dict) and inst.get("state") is not None:
            return str(inst.get("state", ""))
        if data.get("state") is not None:
            return str(data.get("state", ""))
        return "close"

    def _state_connected(self, state: str) -> bool:
        s = (state or "").strip().upper()
        return s in ("CONNECTED", "OPEN", "READY")

    def _extract_qr_from_payload(self, data: Optional[Any]) -> Optional[Any]:
        """Evolution v2 connect returns `code`/`base64`; older APIs used `qrCode` / `qrcode`."""
        if isinstance(data, list) and data:
            data = data[0]
        if not data or not isinstance(data, dict):
            return None
        qr = (
            data.get("qrCode")
            or data.get("qrcode")
            or data.get("qrOrCode")
            or data.get("base64")
            or data.get("code")
        )
        if isinstance(qr, dict):
            qr = qr.get("base64") or qr.get("code") or qr.get("qrCode")
        return qr

    def _normalize_image_string(self, img: Optional[str]) -> Optional[str]:
        if not img or not isinstance(img, str):
            return None
        s = img.strip()
        if not s:
            return None
        if s.startswith("data:image"):
            return s
        if s.startswith(("iVBOR", "/9j/")):
            return f"data:image/png;base64,{s}"
        return s

    def _parse_qr_http_response(self, response: httpx.Response) -> Optional[str]:
        """Evolution may return JSON with base64, or raw PNG/JPEG bytes."""
        if response.status_code != 200:
            return None
        body = response.content or b""
        ct = (response.headers.get("content-type") or "").lower()
        if body[:1] == b"{" or "application/json" in ct:
            try:
                data = response.json()
            except Exception:
                return None
            if not isinstance(data, dict):
                return None
            img = (
                data.get("qrcode")
                or data.get("qrCode")
                or data.get("base64")
                or data.get("code")
            )
            if isinstance(img, dict):
                img = img.get("base64") or img.get("qrcode") or img.get("qrCode")
            return self._normalize_image_string(str(img)) if img else None
        if body.startswith(b"\x89PNG") or body.startswith(b"\xff\xd8\xff") or "image" in ct:
            b64 = base64.b64encode(body).decode("ascii")
            mime = "image/png" if body.startswith(b"\x89PNG") else "image/jpeg"
            return f"data:{mime};base64,{b64}"
        return None

    async def _fetch_qr_image_multi(self) -> Optional[str]:
        """Try common Evolution routes for the QR PNG/base64."""
        client = await self._get_client()
        paths = [
            f"/instance/qrCode/{self.instance_name}",
            f"/instance/qrcode/{self.instance_name}",
        ]
        for path in paths:
            try:
                response = await client.get(path)
                parsed = self._parse_qr_http_response(response)
                if parsed:
                    return parsed
            except Exception as e:
                logger.debug("QR fetch %s: %s", path, e)
        return None

    async def _poll_instance_connect_qr(
        self,
        *,
        max_attempts: int = 55,
        delay_sec: float = 0.55,
    ) -> Optional[str]:
        """
        Evolution API often returns only {\"count\": 0} until Baileys emits the QR.
        Poll GET /instance/connect/{instance} until base64/code appears or attempts exhausted.
        """
        client = await self._get_client()
        path = f"/instance/connect/{self.instance_name}"
        last_obj: Any = None
        for _ in range(max_attempts):
            try:
                response = await client.get(path)
            except Exception as e:
                self._qr_diag["connect_error"] = str(e)[:220]
                return None
            if response.status_code != 200:
                self._qr_diag["connect_error"] = (
                    f"connect HTTP {response.status_code}: {response.text[:220]}"
                )
                return None
            try:
                payload = response.json()
            except Exception:
                payload = None
            last_obj = payload
            if isinstance(payload, list) and payload:
                payload = payload[0]
            if isinstance(payload, dict) and payload.get("pairingCode"):
                self._last_pairing_code = str(payload["pairingCode"])
            raw = self._extract_qr_from_payload(payload)
            if raw:
                img = self._normalize_image_string(str(raw))
                if img:
                    return img
                s = str(raw).strip()
                if len(s) > 60:
                    return self._normalize_image_string(s) or s
            await asyncio.sleep(delay_sec)

        if isinstance(last_obj, dict):
            if (
                last_obj.get("count") == 0
                and not last_obj.get("base64")
                and not last_obj.get("code")
                and not last_obj.get("qrOrCode")
            ):
                self._qr_diag["error"] = (
                    "Evolution returned empty QR (count=0). Update CONFIG_SESSION_PHONE_VERSION in "
                    "docker-compose.yml (value from WhatsApp Web → Menu → Help), run "
                    "`docker compose up -d --force-recreate evolution-api`, then "
                    "`bash scripts/reset_evolution_whatsapp_instance.sh`, and Connect again."
                )
        return None

    async def ensure_whatsapp_instance(self, webhook_url: Optional[str] = None) -> bool:
        """
        Evolution API v2 requires an instance before connect/qrCode works.
        POST /instance/create when connectionState returns 404.
        Optionally configure webhook URL for this instance.
        """
        self._qr_diag.pop("error", None)
        if not self.base_url:
            self._qr_diag["error"] = "EVOLUTION_URL is not set in backend .env"
            return False
        if not self.api_key:
            self._qr_diag["error"] = "EVOLUTION_API_KEY is not set in backend .env"
            return False
        try:
            client = await self._get_client()
            r = await client.get(f"/instance/connectionState/{self.instance_name}")
            self._qr_diag["connectionState_http"] = r.status_code
            if r.status_code == 200:
                # Instance exists - ensure webhook is configured
                if webhook_url:
                    await self._configure_instance_webhook(client, webhook_url)
                return True
            if r.status_code == 401:
                self._qr_diag["error"] = "Evolution API returned 401 — verify EVOLUTION_API_KEY"
                return False
            if r.status_code == 404:
                # Create new instance with webhook configuration
                create_payload = {
                    "instanceName": self.instance_name,
                    "integration": "WHATSAPP-BAILEYS",
                    "qrcode": True,
                }
                if webhook_url:
                    create_payload["webhook"] = {
                        "url": webhook_url,
                        "webhookByEvents": False,
                        "webhookEvents": ["messages.upsert", "connection.update"],
                    }
                cr = await client.post(
                    "/instance/create",
                    json=create_payload,
                )
                self._qr_diag["create_http"] = cr.status_code
                if cr.status_code in (200, 201):
                    return True
                low = cr.text.lower()
                if cr.status_code == 403 and ("already" in low or "in use" in low):
                    # Instance already exists - try to configure webhook
                    if webhook_url:
                        await self._configure_instance_webhook(client, webhook_url)
                    return True
                self._qr_diag["create_error"] = cr.text[:800]
                logger.warning(
                    "Evolution create instance failed: %s %s",
                    cr.status_code,
                    cr.text[:300],
                )
                return False
            self._qr_diag["connectionState_error"] = r.text[:400]
            return False
        except Exception as e:
            self._qr_diag["error"] = f"Evolution unreachable ({self.base_url}): {e}"
            logger.warning("ensure_whatsapp_instance: %s", e)
            return False

    async def _configure_instance_webhook(self, client: httpx.AsyncClient, webhook_url: str) -> bool:
        """Configure webhook URL for an existing Evolution instance."""
        try:
            settings_response = await client.get(f"/instance/settings/{self.instance_name}")
            if settings_response.status_code != 200:
                return False

            current_settings = settings_response.json()
            current_webhook_url = current_settings.get("webhook", {}).get("url", "")

            # Skip if webhook URL is already correctly configured
            if webhook_url in current_webhook_url:
                return True

            # Update webhook settings
            update_payload = {
                "instanceName": self.instance_name,
                "webhook": {
                    "url": webhook_url,
                    "webhookByEvents": False,
                    "webhookEvents": ["messages.upsert", "connection.update"],
                    "enabled": True,
                },
            }
            update_response = await client.post(
                "/instance/settings",
                json=update_payload,
            )
            if update_response.status_code in (200, 201):
                logger.info(f"Configured webhook for instance {self.instance_name}: {webhook_url}")
                return True
            logger.warning(f"Failed to configure webhook for {self.instance_name}: {update_response.status_code}")
            return False
        except Exception as e:
            logger.warning(f"Failed to configure webhook for {self.instance_name}: {e}")
            return False

    async def configure_webhook(self, webhook_url: str) -> bool:
        """Public method to configure webhook URL for this instance."""
        client = await self._get_client()
        return await self._configure_instance_webhook(client, webhook_url)

    async def poll_live_qr(self) -> Optional[str]:
        """
        Load QR for pairing when connectionState omits it (common on Evolution v2).

        Order: ensure instance -> qrCode endpoints -> poll GET /instance/connect (Baileys emits QR asynchronously).
        """
        self._last_pairing_code = None
        try:
            await self.ensure_whatsapp_instance()

            img = await self._fetch_qr_image_multi()
            if img:
                return img

            client = await self._get_client()
            snap = await client.get(f"/instance/connect/{self.instance_name}")
            if snap.status_code == 200:
                try:
                    payload = snap.json()
                except Exception:
                    payload = {}
                if isinstance(payload, list) and payload:
                    payload = payload[0]
                if isinstance(payload, dict) and payload.get("pairingCode"):
                    self._last_pairing_code = str(payload["pairingCode"])
                raw = self._extract_qr_from_payload(payload)
                if raw:
                    img = self._normalize_image_string(str(raw)) or str(raw)
                    if img:
                        return img

            img = await self._fetch_qr_image_multi()
            if img:
                return img

            logger.debug("poll_live_qr: no QR for instance=%s", self.instance_name)
            return None
        except Exception as e:
            self._qr_diag["error"] = str(e)
            logger.warning("poll_live_qr failed for %s: %s", self.instance_name, e)
            return None

    async def get_connection_status(self) -> dict:
        """Get WhatsApp connection status"""
        try:
            client = await self._get_client()
            response = await client.get(f"/instance/connectionState/{self.instance_name}")

            if response.status_code == 200:
                data = response.json()
                state = self._extract_instance_state(data)

                # Detect state changes
                state_changed = self._last_known_state is not None and self._last_known_state != state
                old_state = self._last_known_state
                self._last_known_state = state

                qr_raw = (
                    data.get("qrCode")
                    or data.get("qrcode")
                    or (
                        data.get("instance", {}).get("qrCode")
                        if isinstance(data.get("instance"), dict)
                        else None
                    )
                )

                return {
                    "connected": self._state_connected(state),
                    "status": state,
                    "qr_code": qr_raw,
                    "message": self._get_status_message(state),
                    "state_changed": state_changed,
                    "old_state": old_state,
                }
            return {"connected": False, "status": "ERROR", "message": "Failed to get status"}
        except Exception as e:
            logger.error(f"Failed to get connection status: {e}")
            return {"connected": False, "status": "ERROR", "message": str(e)}

    def reset_state_tracking(self):
        """Reset state tracking after session reset/reconnect"""
        self._last_known_state = None
        self._qr_diag = {}

    def _get_status_message(self, state: str) -> str:
        """Get human-readable status message"""
        key = (state or "").strip().upper()
        messages = {
            "CONNECTED": "WhatsApp is connected and ready",
            "OPEN": "WhatsApp is connected and ready",
            "DISCONNECTED": "WhatsApp is disconnected",
            "CLOSE": "WhatsApp is disconnected",
            "CLOSED": "WhatsApp is disconnected",
            "CONNECTING": "WhatsApp is connecting...",
            "DISCONNECTING": "WhatsApp is disconnecting...",
            "QRCODE": "Waiting for QR scan",
            "DISCONNECTED_BY_OWNER": "Disconnected by owner",
        }
        return messages.get(key, f"Status: {state}")

    async def generate_qr_code(self, webhook_url: Optional[str] = None) -> dict:
        """Generate QR code for WhatsApp pairing (Evolution v2 + legacy v1).

        Args:
            webhook_url: Optional URL to configure for receiving webhooks on this instance.
        """
        try:
            await self.ensure_whatsapp_instance(webhook_url=webhook_url)

            status = await self.get_connection_status()

            if status.get("connected"):
                return {
                    "success": True,
                    "qr_code": None,
                    "already_connected": True,
                    "message": "WhatsApp is already connected",
                }

            if status.get("qr_code"):
                return {
                    "success": True,
                    "qr_code": status["qr_code"],
                    "message": "QR code available",
                }

            img = await self.get_qr_code_image()
            if img:
                return {
                    "success": True,
                    "qr_code": img,
                    "pairing_code": self.get_pairing_code(),
                    "message": "QR code generated",
                }

            img = await self._poll_instance_connect_qr()
            if img:
                return {
                    "success": True,
                    "qr_code": img,
                    "pairing_code": self.get_pairing_code(),
                    "message": "QR code generated",
                }

            hint = self.evolution_user_hint()
            return {
                "success": False,
                "error": "No QR payload from Evolution API",
                "details": hint or "Timed out waiting for QR from Evolution",
                "pairing_code": self.get_pairing_code(),
            }

        except Exception as e:
            logger.error(f"Failed to generate QR: {e}")
            return {"success": False, "error": str(e)}

    async def get_qr_code_image(self) -> Optional[str]:
        """Get QR code as base64 image (PNG) from Evolution."""
        try:
            return await self._fetch_qr_image_multi()
        except Exception as e:
            logger.error("Failed to get QR image: %s", e)
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