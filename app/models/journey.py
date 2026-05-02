"""Journey Database Models"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON
from app.core.database import Base


class JourneyConfig(Base):
    """Journey module configuration per tenant."""
    __tablename__ = "journey_config"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), unique=True, nullable=False, index=True)

    # Enabled/disabled
    is_enabled = Column(Boolean, default=True)

    # Message timing (in UTC hour, 0-23)
    morning_message_hour = Column(Integer, default=8)    # 8 AM
    breakfast_hour = Column(Integer, default=7)           # 7 AM
    lunch_hour = Column(Integer, default=11)           # 11 AM
    dinner_hour = Column(Integer, default=18)          # 6 PM
    evening_hour = Column(Integer, default=20)          # 8 PM

    # Hotel location for weather (lat/lng)
    hotel_latitude = Column(String(50), nullable=True)
    hotel_longitude = Column(String(50), nullable=True)
    hotel_city = Column(String(100), nullable=True)

    # Message types enabled
    enable_weather_based = Column(Boolean, default=True)
    enable_meal_reminders = Column(Boolean, default=True)
    enable_status_messages = Column(Boolean, default=True)
    enable_conversation = Column(Boolean, default=True)

    # Max messages per guest per day
    max_messages_per_day = Column(Integer, default=5)

    # Guest filters
    include_due_in = Column(Boolean, default=True)
    include_arrived = Column(Boolean, default=True)
    include_stayover = Column(Boolean, default=True)
    include_checkout_today = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JourneySchedule(Base):
    """Scheduled message templates per tenant."""
    __tablename__ = "journey_schedules"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False, index=True)

    # Schedule info
    name = Column(String(100), nullable=False)
    message_type = Column(String(50), nullable=False)  # morning, breakfast, lunch, dinner, evening, custom
    hour = Column(Integer, nullable=False)            # Hour of day (0-23)
    minute = Column(Integer, default=0)
    day_type = Column(String(50), default="daily")   # daily, weekdays, weekends

    # Message rules
    weather_based = Column(Boolean, default=False)   # Modify message based on weather
    status_based = Column(Boolean, default=True)     # Customize by guest status

    # Active status
    is_active = Column(Boolean, default=True)

    # Default message template (can be overridden by AI)
    default_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JourneyMessageLog(Base):
    """Log of all journey messages sent."""
    __tablename__ = "journey_message_logs"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False, index=True)

    # Guest info
    guest_id = Column(String(100), nullable=True)      # From booking API
    guest_name = Column(String(255), nullable=True)
    guest_mobile = Column(String(50), nullable=True)
    room_number = Column(String(50), nullable=True)

    # Message details
    message_type = Column(String(50), nullable=False)  # morning, lunch, welcome, etc.
    direction = Column(String(20), default="outbound")  # outbound, inbound
    content = Column(Text, nullable=False)

    # Context used
    weather = Column(JSON, nullable=True)             # Weather data used
    guest_status = Column(String(50), nullable=True) # DueIn, Arrived, StayOver, etc.

    # Status
    sent_at = Column(DateTime, nullable=True)
    delivered = Column(Boolean, default=False)
    read = Column(Boolean, default=False)

    # AI generation details
    ai_generated = Column(Boolean, default=False)
    wiki_context = Column(JSON, nullable=True)        # Wiki pages used for context

    created_at = Column(DateTime, default=datetime.utcnow)


class JourneyConversation(Base):
    """Conversation threads with guests."""
    __tablename__ = "journey_conversations"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False, index=True)

    # Guest identification
    guest_id = Column(String(100), nullable=True)
    guest_name = Column(String(255), nullable=True)
    guest_mobile = Column(String(50), nullable=False, index=True)
    room_number = Column(String(50), nullable=True)

    # Conversation state
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Guest preferences (learned from conversation)
    preferences = Column(JSON, nullable=True)         # {food: "vegetarian", pool: true}
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JourneyMessage(Base):
    """Individual messages in a conversation."""
    __tablename__ = "journey_messages"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=False, index=True)

    # Message
    direction = Column(String(20), nullable=False)    # inbound, outbound
    content = Column(Text, nullable=False)

    # AI response details
    ai_generated = Column(Boolean, default=False)
    agent_response = Column(Text, nullable=True)
    wiki_sources = Column(JSON, nullable=True)       # Sources used
    web_search_used = Column(Boolean, default=False)

    # Timing
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# Message Type Constants
# =============================================================================

class MessageType:
    # Time-based
    MORNING = "morning"
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    EVENING = "evening"

    # Status-based
    DUE_IN = "due_in"
    WELCOME = "welcome"
    STAY_REMINDER = "stay_reminder"
    CHECKOUT = "checkout"
    FEEDBACK = "feedback"
    GOODBYE = "goodbye"

    # Special
    WEATHER_ALERT = "weather_alert"
    ACTIVITY_PROMO = "activity_promo"
    CONVERSATION = "conversation"  # AI-generated response


class GuestStatus:
    DUE_IN = "Due In"
    CONFIRMED = "Confirmed"
    ARRIVED = "Arrived"
    STAYOVER = "StayOver"
    CHECKOUT_TODAY = "Checkout Today"
    CHECKED_OUT = "CheckedOut"


class TimeOfDay:
    MORNING = "morning"      # 5-11
    AFTERNOON = "afternoon"   # 12-16
    EVENING = "evening"      # 17-20
    NIGHT = "night"         # 21-4

    @staticmethod
    def get_time_of_day(hour: int) -> str:
        if 5 <= hour < 12:
            return TimeOfDay.MORNING
        elif 12 <= hour < 17:
            return TimeOfDay.AFTERNOON
        elif 17 <= hour < 21:
            return TimeOfDay.EVENING
        else:
            return TimeOfDay.NIGHT


class WeatherCondition:
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    COLD = "cold"
    HOT = "hot"
    UNKNOWN = "unknown"

    @staticmethod
    def from_code(code: int) -> str:
        """Convert OpenWeather condition code to our categories."""
        if 200 <= code < 300:
            return WeatherCondition.RAINY  # Thunderstorm
        elif 300 <= code < 600:
            return WeatherCondition.RAINY   # Drizzle/Rain
        elif 600 <= code < 700:
            return WeatherCondition.COLD    # Snow
        elif code == 800:
            return WeatherCondition.SUNNY   # Clear
        elif 801 <= code < 900:
            return WeatherCondition.CLOUDY  # Clouds
        return WeatherCondition.UNKNOWN