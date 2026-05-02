"""Booking API Routes - Guest Management and External API Integration"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import Tenant
from app.api.deps import get_current_tenant
from app.services.booking_service import (
    get_active_guests,
    get_guest_by_mobile,
    get_guest_by_room,
    get_guest_by_id,
    get_guest_journey_status,
    get_todays_bookings,
    get_guests_by_status,
    sync_guests_to_db,
)
from app.services.inika_client import fetch_guest_inventory, fetch_todays_bookings

router = APIRouter(prefix="/booking", tags=["Booking"])


# =============================================================================
# Schemas
# =============================================================================

class GuestResponse(BaseModel):
    id: str
    tid: Optional[str] = None
    rid: Optional[str] = None
    room: Optional[str] = None
    gname: Optional[str] = None
    mobile: Optional[str] = None
    gstatus: Optional[str] = None
    gcount: Optional[str] = None
    btype: Optional[str] = None
    sub_booking_id: Optional[str] = None
    driver_tag: Optional[str] = None
    cindate: Optional[str] = None
    coutdate: Optional[str] = None

    class Config:
        from_attributes = True


class JourneyResponse(BaseModel):
    guest_name: Optional[str] = None
    room: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    status: Optional[str] = None
    guests_count: Optional[str] = None
    booking_type: Optional[str] = None
    milestones: list = []


class SyncResponse(BaseModel):
    status: str
    synced: Optional[int] = None
    total: Optional[int] = None
    error: Optional[str] = None


# =============================================================================
# External API Endpoints
# =============================================================================

@router.post("/sync", response_model=SyncResponse)
async def sync_guests_from_external_api(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch guest inventory from external booking API and sync to local database.
    """
    result = await fetch_guest_inventory(str(current_tenant.id))

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))

    try:
        import json
        data = result.get("data", "")

        # Parse response data
        if isinstance(data, str):
            guest_data = json.loads(data)
        else:
            guest_data = data

        if not isinstance(guest_data, list):
            raise HTTPException(status_code=500, detail="Invalid data format from API")

        # Sync to database
        synced = await sync_guests_to_db(str(current_tenant.id), guest_data)

        return SyncResponse(
            status="ok",
            synced=synced,
            total=len(guest_data)
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse API response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch")
async def fetch_guests_from_api(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch guest inventory from external API (without syncing).
    Returns raw data from the external booking system.
    """
    result = await fetch_guest_inventory(str(current_tenant.id))
    return result


# =============================================================================
# Guest Endpoints
# =============================================================================

@router.get("/guests")
async def list_guests(
    status: str | None = None,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    List all guests. Optionally filter by status.
    Status options: Arrived, Confirmed, StayOver, Due In, CheckedOut
    """
    if status:
        guests = await get_guests_by_status(str(current_tenant.id), status)
    else:
        guests = await get_active_guests(str(current_tenant.id))

    return {
        "guests": guests,
        "total": len(guests)
    }


@router.get("/guests/today")
async def get_today_bookings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get today's check-ins and check-outs.
    """
    bookings = await get_todays_bookings(str(current_tenant.id))
    return {
        "bookings": bookings,
        "total": len(bookings)
    }


@router.get("/guests/{guest_id}", response_model=GuestResponse)
async def get_guest(
    guest_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get guest details by ID.
    """
    guest = await get_guest_by_id(str(current_tenant.id), guest_id)

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    return guest


@router.get("/guests/room/{room}")
async def get_guest_by_room_number(
    room: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current guest in a specific room.
    """
    guest = await get_guest_by_room(str(current_tenant.id), room)

    if not guest:
        raise HTTPException(status_code=404, detail="No active guest in this room")

    return guest


@router.get("/guests/phone/{mobile}")
async def get_guest_by_phone(
    mobile: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Find guest by mobile number.
    """
    guest = await get_guest_by_mobile(str(current_tenant.id), mobile)

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    return guest


@router.get("/guests/{guest_id}/journey")
async def get_guest_journey(
    guest_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get guest journey status with milestones.
    """
    journey = await get_guest_journey_status(str(current_tenant.id), guest_id)

    if "error" in journey:
        raise HTTPException(status_code=404, detail=journey["error"])

    return journey


# =============================================================================
# Statistics Endpoints
# =============================================================================

@router.get("/stats")
async def get_booking_stats(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get booking statistics for the tenant.
    """
    guests = await get_active_guests(str(current_tenant.id))

    stats = {
        "total_active": len(guests),
        "arrived": len([g for g in guests if g.get("gstatus") == "Arrived"]),
        "confirmed": len([g for g in guests if g.get("gstatus") == "Confirmed"]),
        "stayover": len([g for g in guests if g.get("gstatus") == "StayOver"]),
        "due_in": len([g for g in guests if g.get("gstatus") == "Due In"]),
    }

    today_bookings = await get_todays_bookings(str(current_tenant.id))
    stats["today_checkins"] = len([b for b in today_bookings if b.get("cindate", "").startswith(date.today().isoformat())])
    stats["today_checkouts"] = len([b for b in today_bookings if b.get("coutdate", "").startswith(date.today().isoformat())])

    return stats


# =============================================================================
# Booking Status Types
# =============================================================================
"""
Available guest statuses:
- "Due In" - Booking confirmed, guest hasn't arrived
- "Confirmed" - Booking confirmed
- "Arrived" - Guest has checked in
- "StayOver" - Guest currently staying
- "CheckedOut" - Guest has checked out

Booking types (btype):
- "Individual"
- "Group"
- "Corporate"
- etc.
"""