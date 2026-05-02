"""Message Generator - AI-powered contextual message generation"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import LLMService
from app.services.wiki_service import WikiService
from app.services.journey.weather_service import WeatherService, get_weather
from app.services.journey.guest_selector import format_guest_for_message
from app.models.journey import MessageType, WeatherCondition, TimeOfDay


class MessageGenerator:
    """Generate contextual journey messages using AI."""

    def __init__(
        self,
        db: AsyncSession = None,
        llm_service: LLMService = None,
        wiki_service: WikiService = None
    ):
        self.db = db
        self.llm = llm_service or LLMService()
        self.wiki = wiki_service or WikiService(db)
        self.weather_service = WeatherService()

    async def generate_journey_message(
        self,
        message_type: str,
        tenant_id: str,
        guest: dict,
        weather: dict = None,
        additional_context: str = None,
    ) -> dict[str, Any]:
        """
        Generate a contextual journey message.

        Args:
            message_type: Type of message (morning, lunch, welcome, etc.)
            tenant_id: Tenant ID
            guest: Guest data from booking
            weather: Current weather data (optional)
            additional_context: Extra context for the message

        Returns:
            Dict with message content and metadata
        """
        # Format guest data
        guest_info = format_guest_for_message(guest)

        # Build context
        context_parts = []

        # Guest status context
        status_context = self._get_status_context(message_type, guest_info)
        context_parts.append(status_context)

        # Weather context
        if weather and weather.get("status") == "ok":
            weather_context = self._get_weather_context(weather)
            context_parts.append(weather_context)

        # Hotel info from wiki (if available)
        if self.db:
            wiki_context = await self._get_hotel_context(message_type, tenant_id)
            if wiki_context:
                context_parts.append(wiki_context)

        # Additional custom context
        if additional_context:
            context_parts.append(additional_context)

        # Combine context
        full_context = "\n".join(context_parts)

        # Generate message using LLM
        message = await self._generate_with_llm(message_type, guest_info, full_context)

        return {
            "message": message,
            "message_type": message_type,
            "guest_name": guest_info["name"],
            "room": guest_info["room"],
            "weather_context": weather if weather else None,
            "ai_generated": True,
        }

    async def generate_conversation_response(
        self,
        tenant_id: str,
        guest: dict,
        user_message: str,
        conversation_history: list = None,
    ) -> dict[str, Any]:
        """
        Generate AI response for guest conversation.
        Uses RAG from wiki for accurate hotel information.
        """
        guest_info = format_guest_for_message(guest)

        # Build system prompt for conversation
        system_prompt = self._build_conversation_system_prompt(guest_info)

        # Get relevant wiki context for the question
        wiki_context = ""
        if self.db:
            wiki_results = await self.wiki.query(
                tenant_id=tenant_id,
                query=user_message,
                max_results=3
            )
            if wiki_results.get("answer"):
                wiki_context = f"\n\nHotel Information:\n{wiki_results['answer']}"
                sources = wiki_results.get("sources", [])

        # Build conversation
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages
                messages.append({
                    "role": "user" if msg.get("direction") == "inbound" else "assistant",
                    "content": msg.get("content", "")
                })

        messages.append({"role": "user", "content": user_message})

        # Generate response
        response = await self.llm.chat(
            messages=messages,
            system_override=system_prompt
        )

        return {
            "response": response,
            "wiki_context": wiki_context,
            "guest": guest_info,
        }

    def _get_status_context(self, message_type: str, guest: dict) -> str:
        """Build context based on guest status and message type."""
        status = guest.get("status", "")
        name = guest.get("name", "Guest")

        contexts = {
            MessageType.DUE_IN: f"Guest '{name}' is expected to arrive. They haven't checked in yet. Be welcoming and exciting about their upcoming visit. Check-in is on {guest.get('check_in', 'TBD')}.",
            MessageType.WELCOME: f"Guest '{name}' just arrived! Room {guest.get('room', '')}. Make them feel at home and briefly mention hotel highlights.",
            MessageType.MORNING: f"Guest '{name}' is staying in Room {guest.get('room', '')}. Status: {status}. It's morning - greet them warmly, mention today's weather and activities.",
            MessageType.BREAKFAST: f"It's breakfast time for guest '{name}' in Room {guest.get('room', '')}. Describe today's breakfast offerings. Mention if weather is good for outdoor dining.",
            MessageType.LUNCH: f"It's lunch time for guest '{name}' in Room {guest.get('room', '')}. Describe today's lunch menu. Consider weather for recommendations.",
            MessageType.DINNER: f"It's dinner time for guest '{name}' in Room {guest.get('room', '')}. Describe today's dinner options. Make it appetizing!",
            MessageType.EVENING: f"It's evening for guest '{name}' in Room {guest.get('room', '')}. Mention evening activities, dinner options, or relaxation opportunities.",
            MessageType.CHECKOUT: f"Guest '{name}' in Room {guest.get('room', '')} is checking out today ({guest.get('check_out', '')}). Thank them and invite them to return.",
            MessageType.FEEDBACK: f"Guest '{name}' is about to leave. Ask about their stay and make them feel valued.",
        }

        return contexts.get(message_type, f"Guest '{name}' status: {status}")

    def _get_weather_context(self, weather: dict) -> str:
        """Build weather context for message generation."""
        temp = weather.get("temperature", 20)
        condition = weather.get("condition", "Clear")
        description = weather.get("description", "")
        city = weather.get("city", "")

        return f"""
Current Weather{' in ' + city if city else ''}:
- Temperature: {temp}°C
- Condition: {condition} ({description})

Weather-based recommendations should be natural and helpful, not pushy.
"""

    async def _get_hotel_context(self, message_type: str, tenant_id: str) -> str:
        """Get relevant hotel info from wiki based on message type."""
        search_queries = {
            MessageType.MORNING: "breakfast menu morning activities pool",
            MessageType.BREAKFAST: "breakfast menu items restaurant",
            MessageType.LUNCH: "lunch menu restaurant today",
            MessageType.DINNER: "dinner menu restaurant tonight",
            MessageType.EVENING: "evening activities entertainment spa",
            MessageType.WELCOME: "hotel amenities services highlights",
        }

        query = search_queries.get(message_type, "hotel amenities restaurant pool")
        if query:
            results = await self.wiki.query(tenant_id=tenant_id, query=query, max_results=2)
            if results.get("answer"):
                return f"\nHotel Information:\n{results['answer'][:500]}"  # Limit context

        return ""

    async def _generate_with_llm(
        self,
        message_type: str,
        guest: dict,
        context: str
    ) -> str:
        """Use LLM to generate the actual message."""
        prompts = {
            MessageType.MORNING: f"""Generate a short, friendly morning greeting message for hotel guests.

Context:
{context}

Requirements:
- Max 100 characters (like a WhatsApp message)
- Include guest name naturally
- Mention weather if relevant
- Include a subtle call-to-action (e.g., pool, restaurant, activities)
- Warm and welcoming tone

Output just the message, no explanations.""",

            MessageType.BREAKFAST: f"""Generate a short breakfast reminder message for hotel guests.

Context:
{context}

Requirements:
- Max 80 characters
- Mention breakfast and timing
- Include a诱人的 food mention
- Like a friendly WhatsApp message

Output just the message.""",

            MessageType.LUNCH: f"""Generate a short lunch announcement message for hotel guests.

Context:
{context}

Requirements:
- Max 80 characters
- Mention lunch and current time
- Highlight a specific dish or menu
- Friendly, appetizing tone

Output just the message.""",

            MessageType.DINNER: f"""Generate a short dinner invitation message for hotel guests.

Context:
{context}

Requirements:
- Max 80 characters
- Mention dinner and timing
- Make it sound appealing
- Include restaurant hint

Output just the message.""",

            MessageType.EVENING: f"""Generate a short evening message for hotel guests.

Context:
{context}

Requirements:
- Max 100 characters
- Mention evening activities or dinner
- Relaxing, cozy tone
- Include weather if relevant

Output just the message.""",

            MessageType.WELCOME: f"""Generate a welcoming message for a guest who just arrived.

Context:
{context}

Requirements:
- Max 120 characters
- Exciting and warm
- Mention 1-2 hotel highlights
- Room number naturally included

Output just the message.""",

            MessageType.DUE_IN: f"""Generate an anticipation message for guests arriving soon.

Context:
{context}

Requirements:
- Max 100 characters
- Exciting about their upcoming visit
- Mention something special about the hotel
- Warm and welcoming

Output just the message.""",

            MessageType.CHECKOUT: f"""Generate a checkout reminder message.

Context:
{context}

Requirements:
- Max 100 characters
- Thank them warmly
- Mention late checkout if applicable
- Invite them to return

Output just the message.""",
        }

        prompt = prompts.get(message_type)
        if not prompt:
            prompt = f"""Generate a short, friendly hotel message.

Guest: {guest.get('name', 'Guest')}
Room: {guest.get('room', '')}

Context:
{context}

Requirements:
- Max 80 characters
- Warm and friendly
- WhatsApp message style

Output just the message."""

        response = await self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
        )

        return response.strip()

    def _build_conversation_system_prompt(self, guest: dict) -> str:
        """Build system prompt for AI conversations."""
        return f"""You are a friendly hotel concierge assistant named "Inika" at a boutique hotel.

Guest Information:
- Name: {guest.get('name', 'Guest')}
- Room: {guest.get('room', 'N/A')}
- Status: {guest.get('status', '')}

Guidelines:
1. Be warm, helpful, and professional
2. Use guest's name naturally in conversation
3. Provide accurate hotel information
4. Recommend relevant services and amenities
5. Handle special requests politely (transfer to staff if complex)
6. Keep responses conversational but informative
7. If you don't know something, say you'll check and get back

Current time awareness: Help guests with any questions about the hotel, dining, activities, or services."""


async def generate_journey_message(
    message_type: str,
    tenant_id: str,
    guest: dict,
    weather: dict = None,
    additional_context: str = None,
) -> dict[str, Any]:
    """Convenience function for message generation."""
    generator = MessageGenerator()
    return await generator.generate_journey_message(
        message_type, tenant_id, guest, weather, additional_context
    )


async def generate_conversation_response(
    tenant_id: str,
    guest: dict,
    user_message: str,
    conversation_history: list = None,
) -> dict[str, Any]:
    """Convenience function for conversation responses."""
    generator = MessageGenerator()
    return await generator.generate_conversation_response(
        tenant_id, guest, user_message, conversation_history
    )