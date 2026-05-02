"""Booking Service - Guest Management from External API"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Column, String, Integer, DateTime, Text, select, and_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, AsyncSessionLocal


class GuestInventory(Base):
    """Local cache of guest inventory from external booking API."""
    __tablename__ = "guest_inventory"

    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(36), primary_key=True)  # Part of composite key
    tid = Column(String(100))
    rid = Column(String(100))
    room = Column(String(50))
    gname = Column(String(255))
    mobile = Column(String(50))
    gstatus = Column(String(50))
    gcount = Column(String(10))
    btype = Column(String(50))
    sub_booking_id = Column(String(100))
    driver_tag = Column(String(100))
    cindate = Column(String(20))
    coutdate = Column(String(20))
    synced_at = Column(Integer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tid": self.tid,
            "rid": self.rid,
            "room": self.room,
            "gname": self.gname,
            "mobile": self.mobile,
            "gstatus": self.gstatus,
            "gcount": self.gcount,
            "btype": self.btype,
            "sub_booking_id": self.sub_booking_id,
            "driver_tag": self.driver_tag,
            "cindate": self.cindate,
            "coutdate": self.coutdate,
            "synced_at": self.synced_at,
        }


# =============================================================================
# Guest Management Functions
# =============================================================================

async def sync_guests_to_db(tenant_id: str, guest_data: list[dict[str, Any]]) -> int:
    """Sync guest data from external API to local database."""
    synced = 0
    now = int(time.time())

    async with AsyncSessionLocal() as session:
        for guest in guest_data:
            # Check if guest exists
            result = await session.execute(
                select(GuestInventory).where(
                    and_(
                        GuestInventory.id == guest.get("id", ""),
                        GuestInventory.tenant_id == tenant_id
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                for key in ["tid", "rid", "room", "gname", "mobile", "gstatus",
                           "gcount", "btype", "sub_booking_id", "driver_tag",
                           "cindate", "coutdate"]:
                    setattr(existing, key, guest.get(key, ""))
                existing.synced_at = now
            else:
                # Create new
                new_guest = GuestInventory(
                    id=guest.get("id", ""),
                    tenant_id=tenant_id,
                    tid=guest.get("tid", ""),
                    rid=guest.get("rid", ""),
                    room=guest.get("room", ""),
                    gname=guest.get("gname", ""),
                    mobile=guest.get("mobile", ""),
                    gstatus=guest.get("gstatus", ""),
                    gcount=guest.get("gcount", ""),
                    btype=guest.get("btype", ""),
                    sub_booking_id=guest.get("SubBookingId", guest.get("sub_booking_id", "")),
                    driver_tag=guest.get("driverTag", ""),
                    cindate=guest.get("cindate", ""),
                    coutdate=guest.get("coutdate", ""),
                    synced_at=now,
                )
                session.add(new_guest)

            synced += 1

        await session.commit()

    return synced


async def get_active_guests(tenant_id: str) -> list[dict[str, Any]]:
    """Get all active guests (Arrived, Confirmed, StayOver, Due In)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.gstatus.in_(["Arrived", "Confirmed", "StayOver", "Due In"])
                )
            ).order_by(GuestInventory.cindate.desc())
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]


async def get_guest_by_mobile(tenant_id: str, mobile: str) -> dict[str, Any] | None:
    """Find guest by mobile number."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.mobile == mobile
                )
            ).order_by(GuestInventory.synced_at.desc()).limit(1)
        )
        guest = result.scalar_one_or_none()
        return guest.to_dict() if guest else None


async def get_guest_by_room(tenant_id: str, room: str) -> dict[str, Any] | None:
    """Find currently staying guest by room number."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.room == room,
                    GuestInventory.gstatus.in_(["Arrived", "StayOver"])
                )
            ).order_by(GuestInventory.synced_at.desc()).limit(1)
        )
        guest = result.scalar_one_or_none()
        return guest.to_dict() if guest else None


async def get_guest_journey_status(tenant_id: str, guest_id: str) -> dict[str, Any]:
    """Get guest journey status with milestones."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    (GuestInventory.id == guest_id) | (GuestInventory.tid == guest_id),
                    GuestInventory.tenant_id == tenant_id
                )
            ).limit(1)
        )
        guest_row = result.scalar_one_or_none()

        if not guest_row:
            return {"error": "Guest not found"}

        guest = guest_row.to_dict()
        checkin = guest.get("cindate", "")
        checkout = guest.get("coutdate", "")
        status = guest.get("gstatus", "")

        journey = {
            "guest_name": guest.get("gname", ""),
            "room": guest.get("room", ""),
            "check_in": checkin,
            "check_out": checkout,
            "status": status,
            "guests_count": guest.get("gcount", "1"),
            "booking_type": guest.get("btype", ""),
            "milestones": [],
        }

        # Build milestones based on status
        if status in ("Arrived", "StayOver"):
            journey["milestones"].append({
                "name": "Checked In",
                "completed": True,
                "time": checkin,
            })
            journey["milestones"].append({
                "name": "Welcome Message",
                "completed": True,
            })
            journey["milestones"].append({
                "name": "Check Out",
                "completed": False,
                "scheduled": checkout,
            })
        elif status == "Confirmed":
            journey["milestones"].append({
                "name": "Check In",
                "completed": False,
                "scheduled": checkin,
            })
            journey["milestones"].append({
                "name": "Check Out",
                "completed": False,
                "scheduled": checkout,
            })
        elif status == "Due In":
            journey["milestones"].append({
                "name": "Check In",
                "completed": False,
                "scheduled": checkin,
            })
            journey["milestones"].append({
                "name": "Check Out",
                "completed": False,
                "scheduled": checkout,
            })

        return journey


async def get_todays_bookings(tenant_id: str) -> list[dict[str, Any]]:
    """Get today's check-ins and check-outs."""
    guests = await get_active_guests(tenant_id)
    today = date.today().isoformat()

    return [
        g for g in guests
        if g.get("cindate", "").startswith(today) or g.get("coutdate", "").startswith(today)
    ]


async def get_guest_by_id(tenant_id: str, guest_id: str) -> dict[str, Any] | None:
    """Find guest by ID."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.id == guest_id
                )
            )
        )
        guest = result.scalar_one_or_none()
        return guest.to_dict() if guest else None


async def get_guests_by_status(tenant_id: str, status: str) -> list[dict[str, Any]]:
    """Get guests by specific status."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.gstatus == status
                )
            ).order_by(GuestInventory.cindate.desc())
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]