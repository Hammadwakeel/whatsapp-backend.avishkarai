"""Server-Sent Events (SSE) manager for real-time WhatsApp updates"""

import asyncio
import json
import logging
from typing import Dict, Set
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE connections for real-time updates"""

    def __init__(self):
        # tenant_id -> set of queue async iterators
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, tenant_id: str) -> asyncio.Queue:
        """Register a new SSE connection for a tenant"""
        queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if tenant_id not in self._connections:
                self._connections[tenant_id] = set()
            self._connections[tenant_id].add(queue)
        logger.info(f"SSE client connected: tenant={tenant_id} (total={len(self._connections.get(tenant_id, []))})")
        return queue

    async def disconnect(self, tenant_id: str, queue: asyncio.Queue):
        """Remove an SSE connection"""
        async with self._lock:
            if tenant_id in self._connections:
                self._connections[tenant_id].discard(queue)
                if not self._connections[tenant_id]:
                    del self._connections[tenant_id]
        logger.info(f"SSE client disconnected: tenant={tenant_id}")

    async def broadcast(self, tenant_id: str, event_type: str, data: dict):
        """Send event to all connected clients for a tenant"""
        async with self._lock:
            connections = list(self._connections.get(tenant_id, []))

        if not connections:
            return

        message = json.dumps({"type": event_type, "data": data})
        for queue in connections:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"SSE queue full for tenant={tenant_id}, dropping event")

    async def broadcast_whatsapp_status(self, tenant_id: str, status: dict):
        """Broadcast WhatsApp connection status update"""
        await self.broadcast(tenant_id, "whatsapp_status", status)

    async def broadcast_new_message(self, tenant_id: str, message: dict):
        """Broadcast new inbound/outbound message"""
        await self.broadcast(tenant_id, "new_message", message)

    async def broadcast_connection_state(self, tenant_id: str, state: str):
        """Broadcast WhatsApp connection state (CONNECTED, DISCONNECTED, etc.)"""
        await self.broadcast(tenant_id, "connection_state", {"state": state})

    def is_connected(self, tenant_id: str) -> bool:
        """Check if any clients are connected for a tenant"""
        return tenant_id in self._connections and len(self._connections[tenant_id]) > 0


# Global SSE manager instance
sse_manager = SSEManager()


async def sse_events(tenant_id: str):
    """Generator for SSE events - yields Server-Sent Events"""
    queue = await sse_manager.connect(tenant_id)

    # Send initial connected event
    yield f"event: connected\ndata: {json.dumps({'type': 'connected', 'tenant_id': tenant_id})}\n\n"

    try:
        while True:
            message = await queue.get()
            yield f"data: {message}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        await sse_manager.disconnect(tenant_id, queue)


def create_sse_response(tenant_id: str) -> StreamingResponse:
    """Create an SSE streaming response for a tenant"""
    return StreamingResponse(
        sse_events(tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
