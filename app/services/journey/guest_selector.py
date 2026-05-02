"""Guest Selector - Get guests from booking API for journey messages"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GuestInventory
from app.models.journey import GuestStatus, JourneyConfig
from app.core.database import AsyncSessionLocal


class GuestSelector:
    """Select and filter guests for journey messaging."""

    def __init__(self, db: AsyncSession = None):
        self.db = db

    async def get_active_guests_for_journey(
        self,
        tenant_id: str,
        include_due_in: bool = True,
        include_arrived: bool = True,
        include_stayover: bool = True,
        include_checkout_today: bool = True,
    ) -> list[dict[str, Any]]:
        """Get all guests who should receive journey messages."""
        statuses = []

        if include_due_in:
            statuses.append(GuestStatus.DUE_IN)
        if include_arrived:
            statuses.append(GuestStatus.ARRIVED)
        if include_stayover:
            statuses.append(GuestStatus.STAYOVER)
        if include_checkout_today:
            statuses.append(GuestStatus.CHECKOUT_TODAY)

        if not self.db:
            async with AsyncSessionLocal() as session:
                return await self._get_guests_by_statuses(session, tenant_id, statuses)
        else:
            return await self._get_guests_by_statuses(self.db, tenant_id, statuses)

    async def _get_guests_by_statuses(
        self,
        db: AsyncSession,
        tenant_id: str,
        statuses: list[str]
    ) -> list[dict[str, Any]]:
        """Get guests filtered by statuses."""
        result = await db.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.gstatus.in_(statuses)
                )
            )
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]

    async def get_guests_by_room(self, tenant_id: str, rooms: list[str]) -> list[dict[str, Any]]:
        """Get guests by room numbers."""
        if not self.db:
            async with AsyncSessionLocal() as session:
                return await self._get_by_rooms(session, tenant_id, rooms)
        else:
            return await self._get_by_rooms(self.db, tenant_id, rooms)

    async def _get_by_rooms(
        self,
        db: AsyncSession,
        tenant_id: str,
        rooms: list[str]
    ) -> list[dict[str, Any]]:
        """Internal method to get guests by rooms."""
        result = await db.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.room.in_(rooms)
                )
            )
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]

    async def get_guests_today_arrivals(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get guests checking in today."""
        from datetime import date
        today = date.today().isoformat()

        if not self.db:
            async with AsyncSessionLocal() as session:
                return await self._get_today_arrivals(session, tenant_id, today)
        else:
            return await self._get_today_arrivals(self.db, tenant_id, today)

    async def _get_today_arrivals(
        self,
        db: AsyncSession,
        tenant_id: str,
        today: str
    ) -> list[dict[str, Any]]:
        """Internal method to get today's arrivals."""
        result = await db.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.cindate == today
                )
            )
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]

    async def get_guests_today_departures(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get guests checking out today."""
        from datetime import date
        today = date.today().isoformat()

        if not self.db:
            async with AsyncSessionLocal() as session:
                return await self._get_today_departures(session, tenant_id, today)
        else:
            return await self._get_today_departures(self.db, tenant_id, today)

    async def _get_today_departures(
        self,
        db: AsyncSession,
        tenant_id: str,
        today: str
    ) -> list[dict[str, Any]]:
        """Internal method to get today's departures."""
        result = await db.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.coutdate == today
                )
            )
        )
        guests = result.scalars().all()
        return [guest.to_dict() for guest in guests]

    async def find_guest_by_mobile(self, tenant_id: str, mobile: str) -> dict[str, Any] | None:
        """Find guest by mobile number for conversation routing."""
        if not self.db:
            async with AsyncSessionLocal() as session:
                return await self._find_by_mobile(session, tenant_id, mobile)
        else:
            return await self._find_by_mobile(self.db, tenant_id, mobile)

    async def _find_by_mobile(
        self,
        db: AsyncSession,
        tenant_id: str,
        mobile: str
    ) -> dict[str, Any] | None:
        """Internal method to find guest by mobile."""
        result = await db.execute(
            select(GuestInventory).where(
                and_(
                    GuestInventory.tenant_id == tenant_id,
                    GuestInventory.mobile == mobile
                )
            ).order_by(GuestInventory.synced_at.desc()).limit(1)
        )
        guest = result.scalar_one_or_none()
        return guest.to_dict() if guest else None


async def get_active_guests_for_journey(
    tenant_id: str,
    include_due_in: bool = True,
    include_arrived: bool = True,
    include_stayover: bool = True,
    include_checkout_today: bool = True,
) -> list[dict[str, Any]]:
    """Convenience function to get active guests."""
    selector = GuestSelector()
    return await selector.get_active_guests_for_journey(
        tenant_id,
        include_due_in,
        include_arrived,
        include_stayover,
        include_checkout_today
    )


def format_guest_for_message(guest: dict) -> dict[str, str]:
    """Format guest data for message generation."""
    return {
        "name": guest.get("gname", "Guest"),
        "room": guest.get("room", ""),
        "status": guest.get("gstatus", ""),
        "check_in": guest.get("cindate", ""),
        "check_out": guest.get("coutdate", ""),
        "mobile": guest.get("mobile", ""),
        "guest_count": guest.get("gcount", "1"),
        "booking_type": guest.get("btype", ""),
    }