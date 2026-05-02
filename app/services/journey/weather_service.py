"""Weather Service - Get weather data for intelligent messaging"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()

# OpenWeatherMap API
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"


class WeatherService:
    """Service for fetching weather data."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get(
            "OPENWEATHER_API_KEY",
            settings.openweather_api_key if hasattr(settings, 'openweather_api_key') else ""
        )

    async def get_current_weather(self, lat: float, lon: float) -> dict[str, Any]:
        """Get current weather for coordinates."""
        if not self.api_key:
            return {"status": "error", "error": "OpenWeather API key not configured"}

        url = f"{OPENWEATHER_BASE_URL}/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric"  # Celsius
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return self._format_weather(data)
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": f"HTTP {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"status": "error", "error": str(e)}

    async def get_weather_by_city(self, city: str) -> dict[str, Any]:
        """Get current weather for a city."""
        if not self.api_key:
            return {"status": "error", "error": "OpenWeather API key not configured"}

        url = f"{OPENWEATHER_BASE_URL}/weather"
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return self._format_weather(data)
        except httpx.HTTPStatusError as e:
            return {"status": "error", "error": f"City not found: {city}"}
        except httpx.RequestError as e:
            return {"status": "error", "error": str(e)}

    def _format_weather(self, data: dict) -> dict[str, Any]:
        """Format OpenWeather response to our format."""
        main = data.get("weather", [{}])[0]
        return {
            "status": "ok",
            "temperature": data.get("main", {}).get("temp"),
            "feels_like": data.get("main", {}).get("feels_like"),
            "humidity": data.get("main", {}).get("humidity"),
            "condition": main.get("main", "Unknown"),
            "description": main.get("description", ""),
            "icon": main.get("icon", ""),
            "code": main.get("id", 0),
            "city": data.get("name", ""),
            "wind_speed": data.get("wind", {}).get("speed", 0),
        }

    def get_weather_category(self, weather: dict) -> str:
        """Categorize weather for messaging."""
        temp = weather.get("temperature", 20)
        code = weather.get("code", 800)

        # Temperature-based
        if temp < 15:
            return "cold"
        elif temp > 30:
            return "hot"

        # Condition-based
        if 200 <= code < 600:
            return "rainy"
        elif code == 800:
            return "sunny"
        elif 801 <= code < 900:
            return "cloudy"

        return "normal"

    def get_weather_advice(self, weather: dict) -> str:
        """Get activity advice based on weather."""
        category = self.get_weather_category(weather)
        temp = weather.get("temperature", 20)

        advice = {
            "sunny": {
                "pool": "Perfect day for our rooftop pool! ☀️🏊",
                "outdoor": "Great weather for outdoor activities!",
                "food": "Try our refreshing summer menu at the poolside restaurant.",
            },
            "cloudy": {
                "pool": "Cloudy but pool is still open!",
                "outdoor": "Nice weather for a walk in our garden.",
                "food": "Try our indoor café with city views.",
            },
            "rainy": {
                "pool": "Rainy day - our spa is the perfect escape! 🛁",
                "outdoor": "Check out our indoor activities and cooking class today.",
                "food": "Warm soup menu is available! Try our comfort food.",
            },
            "cold": {
                "pool": "Pool heated to 28°C - still enjoyable!",
                "outdoor": "Stay warm indoors! Our spa has special winter treatments.",
                "food": "Try our hot chocolate and warm desserts at the café.",
            },
            "hot": {
                "pool": "Beat the heat at our AC pool! ❄️",
                "outdoor": "Stay cool! Free ice drinks at the poolside bar.",
                "food": "Fresh salads and cold beverages recommended!",
            },
        }

        return advice.get(category, {
            "pool": "Check out our pool and spa facilities!",
            "outdoor": "Explore our hotel amenities!",
            "food": "Visit our restaurant for today's special menu.",
        })


async def get_weather(lat: float = None, lon: float = None, city: str = None) -> dict[str, Any]:
    """Convenience function to get weather."""
    service = WeatherService()

    if city:
        return await service.get_weather_by_city(city)
    elif lat and lon:
        return await service.get_current_weather(lat, lon)
    else:
        return {"status": "error", "error": "Provide lat/lon or city"}