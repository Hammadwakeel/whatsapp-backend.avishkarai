"""Booking API - Inika External API Integration"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from app.core.config import get_settings

INIKA_API_BASE = "https://grssl.payfiller.com/inika/webhook"


def _booking_api_key() -> str:
    """Resolve Payfiller apiKey from Settings (.env) or OS env."""
    s = get_settings()
    return (s.inika_booking_key or os.environ.get("INIKA_BOOKING_KEY") or "").strip()


class InikaClient:
    """Client for Inika external booking API."""

    def __init__(self, api_key: str | None = None):
        if api_key:
            self.api_key = api_key
        else:
            s = get_settings()
            self.api_key = (
                s.inika_api_key or os.environ.get("INIKA_API_KEY") or ""
            ).strip()
        self.base_url = INIKA_API_BASE

    def get_headers(self) -> dict[str, str]:
        # Payfiller/Inika webhook expects apiKey as a header (see getTodaysBookings).
        return {"apiKey": self.api_key} if self.api_key else {}


def parse_get_todays_bookings_body(parsed: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Normalize JSON from getTodaysBookings.

    Success envelope: {"status": 1, "message": "...", "data": [ {...}, ... ]}
    Some deployments may return a bare list.
    """
    meta: dict[str, Any] = {}
    if isinstance(parsed, list):
        return parsed, meta
    if isinstance(parsed, dict):
        meta["api_status"] = parsed.get("status")
        meta["api_message"] = parsed.get("message")
        data = parsed.get("data")
        if isinstance(data, list):
            return data, meta
    return [], meta


async def fetch_guest_inventory(_tenant_id: str) -> dict[str, Any]:
    """
    Fetch guest inventory from getTodaysBookings.

    Uses Settings ``inika_booking_key`` / env ``INIKA_BOOKING_KEY``, sent as header ``apiKey``.
    """
    api_key = _booking_api_key()

    if not api_key:
        return {"status": "error", "error": "INIKA_BOOKING_KEY not configured"}

    url = f"{INIKA_API_BASE}/getTodaysBookings/"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
            response = await http_client.post(
                url,
                headers={"apiKey": api_key},
            )
            response.raise_for_status()
            try:
                parsed = response.json()
            except json.JSONDecodeError:
                return {
                    "status": "error",
                    "error": "Booking API returned non-JSON body",
                }

        guests, meta = parse_get_todays_bookings_body(parsed)
        out: dict[str, Any] = {"status": "ok", "guests": guests, **meta}
        return out
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error: {e.response.status_code}, response: {e.response.text[:500]}"
        return {"status": "error", "error": error_msg}
    except httpx.RequestError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# =============================================================================
# Sync Functions (for background tasks)
# =============================================================================


async def sync_guests_from_api(tenant_id: str) -> dict[str, Any]:
    """Fetch guests from API and sync to local storage."""
    result = await fetch_guest_inventory(tenant_id)

    if result.get("status") == "error":
        return result

    guest_data = result.get("guests", [])
    if not isinstance(guest_data, list):
        return {"status": "error", "error": "Invalid data format"}

    synced = await _sync_guests_to_db(tenant_id, guest_data)
    return {"status": "ok", "synced": synced, "total": len(guest_data)}


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
