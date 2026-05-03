"""Journey API Routes - Guest Engagement & Smart Messaging"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import Tenant
from app.api.deps import get_current_tenant
from app.models.journey import (
    JourneyConfig,
    JourneySchedule,
    JourneyMessageLog,
    MessageType,
    GuestStatus,
)
from app.services.journey import (
    JourneyScheduler,
    WeatherService,
    generate_journey_message,
    generate_conversation_response,
    send_journey_message,
    get_active_guests_for_journey,
)

router = APIRouter(prefix="/journey", tags=["Journey"])


async def weather_from_journey_config(db: AsyncSession, tenant_id: str) -> dict:
    """Resolve OpenWeather call from saved JourneyConfig (city or lat/lon)."""
    from sqlalchemy import select

    weather_service = WeatherService()
    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {
            "status": "no_location",
            "temperature": None,
            "condition": None,
            "description": None,
            "city": None,
        }
    city = (config.hotel_city or "").strip()
    if city:
        return await weather_service.get_weather_by_city(city)
    lat_s = config.hotel_latitude
    lon_s = config.hotel_longitude
    if lat_s and lon_s:
        try:
            return await weather_service.get_current_weather(
                float(lat_s), float(lon_s)
            )
        except (TypeError, ValueError):
            return {
                "status": "error",
                "temperature": None,
                "condition": None,
                "description": None,
                "city": None,
            }
    return {
        "status": "no_location",
        "temperature": None,
        "condition": None,
        "description": None,
        "city": None,
    }


def _apply_journey_config_payload(config: JourneyConfig, data: dict[str, Any]) -> None:
    """Merge update payload; allow clearing hotel location fields."""
    loc_keys = frozenset({"hotel_city", "hotel_latitude", "hotel_longitude"})
    for key, value in data.items():
        if not hasattr(config, key):
            continue
        if key in loc_keys:
            if value is None or value == "":
                setattr(config, key, None)
            elif key == "hotel_city":
                setattr(config, key, str(value).strip() or None)
            else:
                setattr(config, key, str(value).strip() or None)
        elif value is not None:
            setattr(config, key, value)


# =============================================================================
# Schemas
# =============================================================================

class JourneyConfigCreate(BaseModel):
    is_enabled: bool = True
    morning_message_hour: int = 8
    breakfast_hour: int = 7
    lunch_hour: int = 11
    dinner_hour: int = 18
    evening_hour: int = 20
    hotel_city: Optional[str] = None
    hotel_latitude: Optional[str] = None
    hotel_longitude: Optional[str] = None
    enable_weather_based: bool = True
    enable_meal_reminders: bool = True
    enable_status_messages: bool = True
    enable_conversation: bool = True
    max_messages_per_day: int = 5
    include_due_in: bool = True
    include_arrived: bool = True
    include_stayover: bool = True
    include_checkout_today: bool = True


class JourneyConfigResponse(BaseModel):
    id: str
    tenant_id: str
    is_enabled: bool
    morning_message_hour: int
    breakfast_hour: int
    lunch_hour: int
    dinner_hour: int
    evening_hour: int
    hotel_city: Optional[str]
    hotel_latitude: Optional[str]
    hotel_longitude: Optional[str]
    enable_weather_based: bool
    enable_meal_reminders: bool
    enable_status_messages: bool
    enable_conversation: bool
    max_messages_per_day: int
    include_due_in: bool
    include_arrived: bool
    include_stayover: bool
    include_checkout_today: bool

    class Config:
        from_attributes = True


class WeatherResponse(BaseModel):
    status: str
    temperature: Optional[float] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None


class SendMessageRequest(BaseModel):
    guest_id: str
    message_type: str = "manual"
    custom_message: Optional[str] = None


class SendMessageResponse(BaseModel):
    status: str
    message: str
    sent_to: Optional[str] = None


class JourneyCycleResponse(BaseModel):
    timestamp: str
    message_type: str
    weather: Optional[dict]
    guests_count: int
    messages_sent: int
    errors: list


# =============================================================================
# Configuration Endpoints
# =============================================================================

@router.get("/config", response_model=JourneyConfigResponse)
async def get_journey_config(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get journey configuration for tenant."""
    from sqlalchemy import select

    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create default config (hotel location set by tenant via UI / API)
        config = JourneyConfig(
            id=str(uuid.uuid4()),
            tenant_id=str(current_tenant.id),
            is_enabled=True,
            hotel_city=None,
        )
        db.add(config)
        await db.commit()

        # Refresh to get generated ID
        await db.refresh(config)

    return config


@router.post("/config", response_model=JourneyConfigResponse)
async def update_journey_config(
    config_data: JourneyConfigCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update journey configuration."""
    from sqlalchemy import select
    from app.services.journey.auto_scheduler import get_auto_scheduler

    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    dump = config_data.model_dump()

    if config:
        _apply_journey_config_payload(config, dump)
    else:
        config = JourneyConfig(
            id=str(current_tenant.id),
            tenant_id=str(current_tenant.id),
        )
        _apply_journey_config_payload(config, dump)
        db.add(config)

    await db.commit()
    await db.refresh(config)

    # Update scheduler with new config
    scheduler = get_auto_scheduler()
    await scheduler.update_tenant_schedule(db, str(current_tenant.id))

    return config


@router.post("/config/enable")
async def enable_journey(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Enable journey messaging."""
    from sqlalchemy import select
    from app.services.journey.auto_scheduler import get_auto_scheduler

    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    if config:
        config.is_enabled = True
    else:
        config = JourneyConfig(
            id=str(current_tenant.id),
            tenant_id=str(current_tenant.id),
            is_enabled=True,
        )
        db.add(config)

    await db.commit()

    # Reschedule if newly created or updated
    scheduler = get_auto_scheduler()
    await scheduler.update_tenant_schedule(db, str(current_tenant.id))

    return {"status": "ok", "message": "Journey enabled"}


@router.post("/config/disable")
async def disable_journey(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Disable journey messaging."""
    from sqlalchemy import select
    from app.services.journey.auto_scheduler import get_auto_scheduler

    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    if config:
        config.is_enabled = False
        await db.commit()

    # Remove from scheduler
    scheduler = get_auto_scheduler()
    scheduler.remove_tenant_schedule(str(current_tenant.id))

    return {"status": "ok", "message": "Journey disabled"}


# =============================================================================
# Weather Endpoint
# =============================================================================

@router.get("/weather", response_model=WeatherResponse)
async def get_current_weather(
    city: str = Query(None),
    lat: float = Query(None),
    lon: float = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get current weather. Query params override saved journey location (city or lat/lon)."""
    weather_service = WeatherService()

    if city:
        weather = await weather_service.get_weather_by_city(city)
    elif lat is not None and lon is not None:
        weather = await weather_service.get_current_weather(lat, lon)
    else:
        weather = await weather_from_journey_config(db, str(current_tenant.id))

    return weather


# =============================================================================
# Guest Message Endpoints
# =============================================================================

@router.get("/guests")
async def list_journey_guests(
    status: str = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List guests eligible for journey messages."""
    status_filter = status.split(",") if status else None

    guests = await get_active_guests_for_journey(str(current_tenant.id))

    if status_filter:
        guests = [g for g in guests if g.get("gstatus") in status_filter]

    return {
        "guests": guests,
        "total": len(guests),
    }


@router.post("/send")
async def send_journey_message_to_guest(
    request: SendMessageRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send a journey message to a specific guest."""
    from sqlalchemy import select
    from app.models import GuestInventory

    # Get guest from booking
    result = await db.execute(
        select(GuestInventory).where(
            GuestInventory.tenant_id == str(current_tenant.id),
            GuestInventory.id == request.guest_id
        )
    )
    guest = result.scalar_one_or_none()

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    guest_data = guest.to_dict()

    weather = await weather_from_journey_config(db, str(current_tenant.id))

    # Generate or use custom message
    if request.custom_message:
        message = request.custom_message
        message_type = "manual"
    else:
        result = await generate_journey_message(
            message_type=request.message_type,
            tenant_id=str(current_tenant.id),
            guest=guest_data,
            weather=weather if weather.get("status") == "ok" else None,
        )
        message = result.get("message", "")
        message_type = request.message_type

    # Send message
    send_result = await send_journey_message(
        tenant_id=str(current_tenant.id),
        guest=guest_data,
        message=message,
        message_type=message_type,
        weather=weather if weather.get("status") == "ok" else None,
    )

    return send_result


@router.post("/send/broadcast")
async def broadcast_journey_message(
    message_type: str = Query("morning"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Broadcast journey message to all active guests."""
    scheduler = JourneyScheduler()

    # Get config for hotel location
    from sqlalchemy import select
    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    hotel_location = None
    if config and config.hotel_city:
        hotel_location = {"city": config.hotel_city}
    elif config and config.hotel_latitude and config.hotel_longitude:
        hotel_location = {"lat": config.hotel_latitude, "lon": config.hotel_longitude}

    # Run journey cycle
    result = await scheduler.run_journey_cycle(
        tenant_id=str(current_tenant.id),
        config=config,
        hotel_location=hotel_location,
    )

    return result


# =============================================================================
# Status-Based Messages
# =============================================================================

@router.post("/send/due-in")
async def send_due_in_messages(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send anticipation messages to guests arriving soon."""
    scheduler = JourneyScheduler()

    from sqlalchemy import select
    result = await db.execute(
        select(JourneyConfig).where(JourneyConfig.tenant_id == str(current_tenant.id))
    )
    config = result.scalar_one_or_none()

    hotel_location = None
    if config and config.hotel_city:
        hotel_location = {"city": config.hotel_city}
    elif config and config.hotel_latitude and config.hotel_longitude:
        hotel_location = {
            "lat": float(config.hotel_latitude),
            "lon": float(config.hotel_longitude),
        }

    result = await scheduler.send_status_based_messages(
        tenant_id=str(current_tenant.id),
        status=GuestStatus.DUE_IN,
        hotel_location=hotel_location,
    )

    return result


@router.post("/send/welcome/{guest_id}")
async def send_welcome_to_guest(
    guest_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Send welcome message to a newly arrived guest."""
    from sqlalchemy import select
    from app.models import GuestInventory

    result = await db.execute(
        select(GuestInventory).where(
            GuestInventory.tenant_id == str(current_tenant.id),
            GuestInventory.id == guest_id
        )
    )
    guest = result.scalar_one_or_none()

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    guest_data = guest.to_dict()

    # Generate welcome message
    result = await generate_journey_message(
        message_type=MessageType.WELCOME,
        tenant_id=str(current_tenant.id),
        guest=guest_data,
    )

    # Send
    send_result = await send_journey_message(
        tenant_id=str(current_tenant.id),
        guest=guest_data,
        message=result.get("message", ""),
        message_type=MessageType.WELCOME,
    )

    return {
        "message": result.get("message", ""),
        **send_result
    }


# =============================================================================
# Message Logs
# =============================================================================

@router.get("/logs")
async def get_message_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    message_type: str = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get journey message logs."""
    from sqlalchemy import select, desc

    query = select(JourneyMessageLog).where(
        JourneyMessageLog.tenant_id == str(current_tenant.id)
    )

    if message_type:
        query = query.where(JourneyMessageLog.message_type == message_type)

    query = query.order_by(desc(JourneyMessageLog.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(JourneyMessageLog).where(
        JourneyMessageLog.tenant_id == str(current_tenant.id)
    )
    if message_type:
        count_query = count_query.where(JourneyMessageLog.message_type == message_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return {
        "logs": [
            {
                "id": log.id,
                "guest_name": log.guest_name,
                "guest_mobile": log.guest_mobile,
                "room_number": log.room_number,
                "message_type": log.message_type,
                "direction": log.direction,
                "content": log.content,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "delivered": log.delivered,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# AI Conversation (for webhook integration)
# =============================================================================

@router.post("/conversation")
async def handle_conversation(
    tenant_id: str,
    mobile: str,
    message: str,
    history: list = None,
):
    """Handle incoming conversation from guest (used by webhook)."""
    from app.services.journey.guest_selector import GuestSelector

    # Find guest by mobile
    selector = GuestSelector()
    guest = await selector.find_guest_by_mobile(tenant_id, mobile)

    if not guest:
        return {
            "response": "I'm sorry, I couldn't find your booking. Please contact reception.",
            "status": "guest_not_found"
        }

    # Generate AI response
    result = await generate_conversation_response(
        tenant_id=tenant_id,
        guest=guest,
        user_message=message,
        conversation_history=history,
    )

    return {
        "response": result.get("response", ""),
        "guest_name": guest.get("gname"),
        "room": guest.get("room"),
        "wiki_context": result.get("wiki_context"),
    }


# =============================================================================
# Auto Scheduler Status
# =============================================================================

@router.get("/scheduler/status")
async def get_scheduler_status(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get auto scheduler status for current tenant."""
    from app.services.journey.auto_scheduler import get_auto_scheduler

    tenant_id = str(current_tenant.id)
    scheduler = get_auto_scheduler()

    # Check if tenant has jobs scheduled
    job_ids = [
        f"{tenant_id}_morning",
        f"{tenant_id}_breakfast",
        f"{tenant_id}_lunch",
        f"{tenant_id}_dinner",
        f"{tenant_id}_evening",
        f"{tenant_id}_due_in_check",
        f"{tenant_id}_checkout_check",
    ]

    scheduled_jobs = []
    for job_id in job_ids:
        try:
            job = scheduler._scheduler.get_job(job_id)
            if job:
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                scheduled_jobs.append({
                    "job_id": job_id,
                    "next_run": next_run,
                    "active": scheduler._active_jobs.get(tenant_id, False),
                })
        except Exception:
            pass

    return {
        "scheduler_running": scheduler._scheduler.running,
        "tenant_scheduled": len(scheduled_jobs) > 0,
        "jobs": scheduled_jobs,
    }