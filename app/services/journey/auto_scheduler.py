"""Auto Scheduler Service - Background job scheduling for Journey Module"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.journey import JourneyConfig, JourneyMessageLog, MessageType
from app.services.journey import JourneyScheduler

logger = logging.getLogger(__name__)


class JourneyAutoScheduler:
    """
    Automatic scheduler for Journey messages.

    This service:
    - Runs scheduled jobs based on tenant's config (morning_message_hour, breakfast_hour, etc.)
    - Handles rate limiting (max_messages_per_day per guest)
    - Tracks message history to avoid duplicates
    - Sends status-based messages (due in, welcome, checkout) automatically
    """

    _instance: Optional["JourneyAutoScheduler"] = None
    _scheduler: Optional[AsyncIOScheduler] = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._initialized = True
        self._active_jobs: dict[str, bool] = {}  # tenant_id -> is_running

    async def initialize(self, db: AsyncSession):
        """Initialize scheduler and load all tenant configs."""
        if self._scheduler.running:
            return

        # Load all active journey configs
        result = await db.execute(
            select(JourneyConfig).where(JourneyConfig.is_enabled == True)
        )
        configs = result.scalars().all()

        for config in configs:
            self._schedule_for_tenant(config)

        # Start the scheduler
        self._scheduler.start()
        logger.info(f"Journey Auto Scheduler started with {len(configs)} tenant configs")

    def _schedule_for_tenant(self, config: JourneyConfig):
        """Schedule all message jobs for a tenant based on their config."""
        tenant_id = config.tenant_id

        # Schedule time-based messages
        self._add_cron_job(
            job_id=f"{tenant_id}_morning",
            hour=config.morning_message_hour,
            minute=0,
            func=self._run_morning_cycle,
            args=[tenant_id, config.hotel_city],
        )

        self._add_cron_job(
            job_id=f"{tenant_id}_breakfast",
            hour=config.breakfast_hour,
            minute=0,
            func=self._run_meal_cycle,
            args=[tenant_id, config.hotel_city, MessageType.BREAKFAST],
        )

        self._add_cron_job(
            job_id=f"{tenant_id}_lunch",
            hour=config.lunch_hour,
            minute=0,
            func=self._run_meal_cycle,
            args=[tenant_id, config.hotel_city, MessageType.LUNCH],
        )

        self._add_cron_job(
            job_id=f"{tenant_id}_dinner",
            hour=config.dinner_hour,
            minute=0,
            func=self._run_meal_cycle,
            args=[tenant_id, config.hotel_city, MessageType.DINNER],
        )

        self._add_cron_job(
            job_id=f"{tenant_id}_evening",
            hour=config.evening_hour,
            minute=0,
            func=self._run_meal_cycle,
            args=[tenant_id, config.hotel_city, MessageType.EVENING],
        )

        # Schedule status-based message checks
        # Check for due-in guests every 30 minutes during working hours (8 AM to 5 PM)
        self._add_cron_job(
            job_id=f"{tenant_id}_due_in_check",
            hour="8,9,10,11,12,13,14,15,16,17",
            minute="0,30",
            func=self._check_due_in_guests,
            args=[tenant_id, config.hotel_city],
        )

        # Check for checkout guests at 10 AM
        self._add_cron_job(
            job_id=f"{tenant_id}_checkout_check",
            hour=10,
            minute=0,
            func=self._check_checkout_guests,
            args=[tenant_id, config.hotel_city],
        )

        logger.info(f"Scheduled {5 + 2} jobs for tenant {tenant_id}")

    def _add_cron_job(
        self,
        job_id: str,
        hour: int | list,
        minute: int | list,
        func,
        args: list,
    ):
        """Add a cron job to the scheduler."""
        try:
            self._scheduler.add_job(
                func,
                CronTrigger(hour=hour, minute=minute),
                id=job_id,
                args=args,
                replace_existing=True,
            )
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")

    async def update_tenant_schedule(self, db: AsyncSession, tenant_id: str):
        """Update schedule when tenant config changes."""
        # Remove existing jobs for this tenant
        self.remove_tenant_schedule(tenant_id)

        # Get updated config
        result = await db.execute(
            select(JourneyConfig).where(JourneyConfig.tenant_id == tenant_id)
        )
        config = result.scalar_one_or_none()

        if config and config.is_enabled:
            self._schedule_for_tenant(config)

    def remove_tenant_schedule(self, tenant_id: str):
        """Remove all scheduled jobs for a tenant."""
        jobs_to_remove = [
            f"{tenant_id}_morning",
            f"{tenant_id}_breakfast",
            f"{tenant_id}_lunch",
            f"{tenant_id}_dinner",
            f"{tenant_id}_evening",
            f"{tenant_id}_due_in_check",
            f"{tenant_id}_checkout_check",
        ]
        for job_id in jobs_to_remove:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

    async def _run_morning_cycle(self, tenant_id: str, city: str):
        """Run morning message cycle."""
        if self._active_jobs.get(tenant_id):
            logger.info(f"Skipping morning cycle for {tenant_id} - already running")
            return

        self._active_jobs[tenant_id] = True
        try:
            logger.info(f"Running morning cycle for tenant {tenant_id}")
            scheduler = JourneyScheduler()
            await scheduler.run_journey_cycle(
                tenant_id=tenant_id,
                hotel_location={"city": city} if city else None,
            )
        except Exception as e:
            logger.error(f"Morning cycle failed for {tenant_id}: {e}")
        finally:
            self._active_jobs[tenant_id] = False

    async def _run_meal_cycle(self, tenant_id: str, city: str, message_type: str):
        """Run meal message cycle (breakfast/lunch/dinner/evening)."""
        if self._active_jobs.get(tenant_id):
            logger.info(f"Skipping {message_type} cycle for {tenant_id} - already running")
            return

        self._active_jobs[tenant_id] = True
        try:
            logger.info(f"Running {message_type} cycle for tenant {tenant_id}")
            scheduler = JourneyScheduler()

            # Get active guests
            from app.services.journey.guest_selector import get_active_guests_for_journey
            guests = await get_active_guests_for_journey(tenant_id)

            # Get weather
            weather = None
            if city:
                from app.services.journey.weather_service import get_weather
                weather = await get_weather(city=city)
                if weather.get("status") != "ok":
                    weather = None

            # Send message to each guest
            for guest in guests:
                # Rate limit check
                if await self._should_send_message(tenant_id, guest.get("mobile"), message_type):
                    from app.services.journey.message_generator import generate_journey_message
                    from app.services.journey.message_sender import send_journey_message

                    message = await generate_journey_message(
                        message_type=message_type,
                        tenant_id=tenant_id,
                        guest=guest,
                        weather=weather,
                    )

                    await send_journey_message(
                        tenant_id=tenant_id,
                        guest=guest,
                        message=message.get("message", ""),
                        message_type=message_type,
                        weather=weather,
                    )

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"{message_type} cycle failed for {tenant_id}: {e}")
        finally:
            self._active_jobs[tenant_id] = False

    async def _check_due_in_guests(self, tenant_id: str, city: str):
        """Check for guests due in and send anticipation messages."""
        if self._active_jobs.get(f"{tenant_id}_due_in"):
            return

        self._active_jobs[f"{tenant_id}_due_in"] = True
        try:
            logger.info(f"Checking due-in guests for tenant {tenant_id}")
            scheduler = JourneyScheduler()
            await scheduler.send_status_based_messages(
                tenant_id=tenant_id,
                status="DueIn",
                hotel_location={"city": city} if city else None,
            )
        except Exception as e:
            logger.error(f"Due-in check failed for {tenant_id}: {e}")
        finally:
            self._active_jobs[f"{tenant_id}_due_in"] = False

    async def _check_checkout_guests(self, tenant_id: str, city: str):
        """Check for guests checking out today and send checkout messages."""
        if self._active_jobs.get(f"{tenant_id}_checkout"):
            return

        self._active_jobs[f"{tenant_id}_checkout"] = True
        try:
            logger.info(f"Checking checkout guests for tenant {tenant_id}")
            scheduler = JourneyScheduler()
            await scheduler.send_status_based_messages(
                tenant_id=tenant_id,
                status="checkout_today",
                hotel_location={"city": city} if city else None,
            )
        except Exception as e:
            logger.error(f"Checkout check failed for {tenant_id}: {e}")
        finally:
            self._active_jobs[f"{tenant_id}_checkout"] = False

    async def _should_send_message(
        self,
        tenant_id: str,
        mobile: str,
        message_type: str,
    ) -> bool:
        """
        Check if we should send a message (rate limiting).
        Returns False if max_messages_per_day would be exceeded.
        """
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            from datetime import datetime, timedelta

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # Count messages sent today to this guest
            result = await db.execute(
                select(JourneyMessageLog)
                .where(JourneyMessageLog.tenant_id == tenant_id)
                .where(JourneyMessageLog.guest_mobile == mobile)
                .where(JourneyMessageLog.created_at >= today_start)
            )
            sent_today = len(result.scalars().all())

            # Check config for max per day
            config_result = await db.execute(
                select(JourneyConfig).where(JourneyConfig.tenant_id == tenant_id)
            )
            config = config_result.scalar_one_or_none()
            max_per_day = config.max_messages_per_day if config else 5

            return sent_today < max_per_day

    def shutdown(self):
        """Shutdown the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Journey Auto Scheduler shutdown")


# Global instance
_auto_scheduler: Optional[JourneyAutoScheduler] = None


def get_auto_scheduler() -> JourneyAutoScheduler:
    """Get the global auto scheduler instance."""
    global _auto_scheduler
    if _auto_scheduler is None:
        _auto_scheduler = JourneyAutoScheduler()
    return _auto_scheduler


async def init_auto_scheduler(db: AsyncSession):
    """Initialize the auto scheduler with database session."""
    scheduler = get_auto_scheduler()
    await scheduler.initialize(db)