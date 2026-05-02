"""Journey Scheduler - Schedule and trigger journey messages"""

from __future__ import annotations

import asyncio
from datetime import datetime, time
from typing import Any, Callable

from app.services.journey.weather_service import WeatherService, get_weather
from app.services.journey.guest_selector import GuestSelector, get_active_guests_for_journey
from app.services.journey.message_generator import MessageGenerator, generate_journey_message
from app.services.journey.message_sender import JourneyMessageSender, send_journey_message
from app.models.journey import (
    JourneyConfig,
    JourneySchedule,
    MessageType,
    TimeOfDay,
    GuestStatus,
)


class JourneyScheduler:
    """
    Scheduler for journey messages.

    Handles:
    - Time-based triggers (morning, breakfast, lunch, dinner, evening)
    - Guest status triggers (due in, arrived, checkout)
    - Weather-based intelligent messaging
    """

    def __init__(self):
        self.weather_service = WeatherService()
        self.guest_selector = GuestSelector()
        self.message_generator = MessageGenerator()
        self.message_sender = JourneyMessageSender()

        # Active schedulers
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def run_journey_cycle(
        self,
        tenant_id: str,
        config: JourneyConfig = None,
        hotel_location: dict = None,
    ) -> dict[str, Any]:
        """
        Run a complete journey message cycle.

        Gets weather, selects guests, generates and sends messages.
        This would typically be called by a background task scheduler.

        Args:
            tenant_id: Tenant ID
            config: Journey configuration (optional)
            hotel_location: {lat, lon} or {city} for weather

        Returns:
            Dict with results of the cycle
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "guests_processed": 0,
            "messages_sent": 0,
            "errors": [],
        }

        # Get weather
        weather = None
        if hotel_location:
            if hotel_location.get("city"):
                weather = await self.weather_service.get_weather_by_city(
                    hotel_location["city"]
                )
            elif hotel_location.get("lat") and hotel_location.get("lon"):
                weather = await self.weather_service.get_current_weather(
                    hotel_location["lat"],
                    hotel_location["lon"]
                )

        results["weather"] = weather

        # Determine message type based on current time
        current_hour = datetime.utcnow().hour
        time_of_day = TimeOfDay.get_time_of_day(current_hour)
        message_type = self._get_message_type_for_hour(current_hour)

        results["message_type"] = message_type

        # Get guests to message
        guest_filter = {
            "include_due_in": True,
            "include_arrived": True,
            "include_stayover": True,
            "include_checkout_today": True,
        }
        if config:
            guest_filter["include_due_in"] = config.include_due_in
            guest_filter["include_arrived"] = config.include_arrived
            guest_filter["include_stayover"] = config.include_stayover
            guest_filter["include_checkout_today"] = config.include_checkout_today

        guests = await get_active_guests_for_journey(tenant_id, **guest_filter)
        results["guests_count"] = len(guests)

        # Generate and send message for each guest
        for guest in guests:
            try:
                # Check if we should message this guest (rate limiting)
                if not self._should_message_guest(tenant_id, guest.get("mobile"), config):
                    continue

                # Generate message
                message_result = await generate_journey_message(
                    message_type=message_type,
                    tenant_id=tenant_id,
                    guest=guest,
                    weather=weather if weather and weather.get("status") == "ok" else None,
                )

                # Send message
                send_result = await send_journey_message(
                    tenant_id=tenant_id,
                    guest=guest,
                    message=message_result.get("message", ""),
                    message_type=message_type,
                    weather=weather if weather and weather.get("status") == "ok" else None,
                )

                if send_result.get("status") == "ok":
                    results["messages_sent"] += 1
                else:
                    results["errors"].append({
                        "guest": guest.get("gname"),
                        "error": send_result.get("error")
                    })

                results["guests_processed"] += 1

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                results["errors"].append({
                    "guest": guest.get("gname", "Unknown"),
                    "error": str(e)
                })

        return results

    async def send_status_based_messages(
        self,
        tenant_id: str,
        status: str,
        hotel_location: dict = None,
    ) -> dict[str, Any]:
        """Send messages based on guest status changes."""
        weather = None
        if hotel_location:
            if hotel_location.get("city"):
                weather = await self.weather_service.get_weather_by_city(
                    hotel_location["city"]
                )

        # Map status to message type
        status_to_type = {
            GuestStatus.DUE_IN: MessageType.DUE_IN,
            GuestStatus.ARRIVED: MessageType.WELCOME,
            GuestStatus.STAYOVER: MessageType.MORNING,
            "checkout_today": MessageType.CHECKOUT,
            "checked_out": MessageType.FEEDBACK,
        }

        message_type = status_to_type.get(status, MessageType.MORNING)

        # Get guests with this status
        guests = await self.guest_selector.get_active_guests_for_journey(
            tenant_id,
            include_due_in=(status == GuestStatus.DUE_IN),
            include_arrived=(status == GuestStatus.ARRIVED),
            include_stayover=(status == GuestStatus.STAYOVER),
            include_checkout_today=(status == "checkout_today"),
        )

        # Filter by specific status
        filtered_guests = [g for g in guests if g.get("gstatus") == status]

        results = {
            "status_type": status,
            "message_type": message_type,
            "guests_count": len(filtered_guests),
            "messages_sent": 0,
            "errors": [],
        }

        for guest in filtered_guests:
            try:
                message_result = await generate_journey_message(
                    message_type=message_type,
                    tenant_id=tenant_id,
                    guest=guest,
                    weather=weather if weather and weather.get("status") == "ok" else None,
                )

                send_result = await send_journey_message(
                    tenant_id=tenant_id,
                    guest=guest,
                    message=message_result.get("message", ""),
                    message_type=message_type,
                    weather=weather if weather and weather.get("status") == "ok" else None,
                )

                if send_result.get("status") == "ok":
                    results["messages_sent"] += 1

                await asyncio.sleep(0.5)

            except Exception as e:
                results["errors"].append(str(e))

        return results

    async def send_weather_alert(
        self,
        tenant_id: str,
        condition: str,
        hotel_location: dict = None,
    ) -> dict[str, Any]:
        """Send weather-based alert to all guests."""
        # Get current weather
        weather = None
        if hotel_location:
            if hotel_location.get("city"):
                weather = await self.weather_service.get_weather_by_city(
                    hotel_location["city"]
                )

        if not weather or weather.get("status") != "ok":
            return {"status": "error", "error": "Weather data not available"}

        guests = await get_active_guests_for_journey(tenant_id)

        results = {
            "message_type": MessageType.WEATHER_ALERT,
            "condition": condition,
            "temperature": weather.get("temperature"),
            "guests_count": len(guests),
            "messages_sent": 0,
        }

        for guest in guests:
            try:
                # Generate weather-specific message
                advice = self.weather_service.get_weather_advice(weather)

                # Customize based on condition
                message = f"☀️ Weather Update!\n\n"
                if condition == "sunny":
                    message += advice["pool"]
                elif condition == "rainy":
                    message += advice["outdoor"]
                elif condition == "cold":
                    message += advice["food"]
                else:
                    message += "Check out our hotel activities for today!"

                send_result = await send_journey_message(
                    tenant_id=tenant_id,
                    guest=guest,
                    message=message,
                    message_type=MessageType.WEATHER_ALERT,
                    weather=weather,
                )

                if send_result.get("status") == "ok":
                    results["messages_sent"] += 1

                await asyncio.sleep(0.5)

            except Exception as e:
                pass

        return results

    def _get_message_type_for_hour(self, hour: int) -> str:
        """Map hour to message type."""
        if 5 <= hour < 10:
            return MessageType.BREAKFAST
        elif 10 <= hour < 14:
            return MessageType.LUNCH
        elif 14 <= hour < 17:
            return MessageType.MORNING  # Afternoon
        elif 17 <= hour < 21:
            return MessageType.DINNER
        elif 21 <= hour < 24:
            return MessageType.EVENING
        else:
            return MessageType.MORNING

    def _should_message_guest(
        self,
        tenant_id: str,
        mobile: str,
        config: JourneyConfig = None,
    ) -> bool:
        """Check if we should message this guest (rate limiting)."""
        # TODO: Implement rate limiting - check JourneyMessageLog
        # For now, allow all messages
        return True


async def run_scheduled_journey(
    tenant_id: str,
    hotel_location: dict = None,
    config: JourneyConfig = None,
) -> dict[str, Any]:
    """Convenience function to run journey cycle."""
    scheduler = JourneyScheduler()
    return await scheduler.run_journey_cycle(tenant_id, config, hotel_location)


async def send_welcome_message(tenant_id: str, guest: dict) -> dict[str, Any]:
    """Send welcome message to a newly arrived guest."""
    weather_service = WeatherService()
    generator = MessageGenerator()
    sender = JourneyMessageSender()

    # Try to get weather
    weather = await get_weather(city="Lahore")  # Default, should be configurable

    # Generate welcome message
    message_result = await generator.generate_journey_message(
        message_type=MessageType.WELCOME,
        tenant_id=tenant_id,
        guest=guest,
        weather=weather if weather.get("status") == "ok" else None,
    )

    # Send
    return await sender.send_journey_message(
        tenant_id=tenant_id,
        guest=guest,
        message=message_result.get("message", ""),
        message_type=MessageType.WELCOME,
        weather=weather if weather.get("status") == "ok" else None,
    )