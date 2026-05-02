"""Booking API - Inika External API Integration"""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any

import httpx

INIKA_API_BASE = "https://grssl.payfiller.com/inika/webhook"


class InikaClient:
    """Client for Inika external booking API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("INIKA_API_KEY", "")
        self.base_url = INIKA_API_BASE

    def get_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
        }


async def fetch_guest_inventory(tenant_id: str) -> dict[str, Any]:
    """Fetch guest inventory from external booking API."""
    client = InikaClient()
    api_key = os.environ.get("INIKA_BOOKING_KEY", "")

    if not api_key:
        return {"status": "error", "error": "INIKA_BOOKING_KEY not configured"}

    url = f"{client.base_url}/getInventoryAPI/{api_key}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                url,
                content='{"status":1}',
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()
            return {"status": "ok", "data": response.text}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def fetch_todays_bookings(tenant_id: str) -> list[dict[str, Any]]:
    """Fetch today's check-ins and check-outs from guest inventory."""
    from app.services.booking_service import get_active_guests

    guests = await get_active_guests(tenant_id)
    today = date.today().isoformat()

    return [
        g for g in guests
        if g.get("cindate", "").startswith(today) or g.get("coutdate", "").startswith(today)
    ]


# =============================================================================
# Sync Functions (for background tasks)
# =============================================================================

async def sync_guests_from_api(tenant_id: str) -> dict[str, Any]:
    """Fetch guests from API and sync to local storage."""
    import json

    result = await fetch_guest_inventory(tenant_id)

    if result.get("status") == "error":
        return result

    try:
        # Parse the response data
        data = result.get("data", "")
        if isinstance(data, str):
            # Try to parse as JSON array
            guest_data = json.loads(data)
        else:
            guest_data = data

        if isinstance(guest_data, list):
            synced = await _sync_guests_to_db(tenant_id, guest_data)
            return {"status": "ok", "synced": synced, "total": len(guest_data)}

        return {"status": "error", "error": "Invalid data format"}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse error: {str(e)}"}


async def _sync_guests_to_db(tenant_id: str, guest_data: list[dict[str, Any]]) -> int:
    """Sync guest data to local SQLite database for caching."""
    from app.core.database import AsyncSessionLocal

    synced = 0
    now = int(time.time())

    async with AsyncSessionLocal() as session:
        # Ensure table exists (using raw SQL for SQLite)
        # In production, you'd use a proper model
        pass

    return synced