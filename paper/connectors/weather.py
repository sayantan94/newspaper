"""Section: weather via Open-Meteo (no API key)."""

from __future__ import annotations

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector
from . import _http

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=1"
_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current_weather=true"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    "&temperature_unit=fahrenheit&timezone=auto&forecast_days=1"
)
_GEO_TTL = 365 * 86400

_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "drizzle", 53: "drizzle", 55: "drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 80: "showers", 81: "showers",
    82: "heavy showers", 95: "thunderstorm",
}


class WeatherConnector(SectionConnector):
    name = "weather"
    title = "WEATHER"

    def fetch(self, ctx: PaperContext) -> Section:
        location = ctx.config.location
        geo_key = f"geocode_{location}"
        geo = ctx.store.cache_get(geo_key, _GEO_TTL) if ctx.store else None
        if geo is None:
            data = _http.get_json(_GEO_URL.format(name=location.replace(" ", "+")))
            results = data.get("results") or []
            if not results:
                return Section(
                    name=self.name, title=self.title,
                    notice=f"unknown location '{location}'",
                )
            geo = {"lat": results[0]["latitude"], "lon": results[0]["longitude"]}
            if ctx.store:
                ctx.store.cache_put(geo_key, geo)
        forecast = _http.get_json(_FORECAST_URL.format(lat=geo["lat"], lon=geo["lon"]))
        current = forecast.get("current_weather", {})
        daily = forecast.get("daily", {})
        desc = _CODES.get(current.get("weathercode"), "")
        now = round(current.get("temperature", 0))
        hi = round((daily.get("temperature_2m_max") or [0])[0])
        lo = round((daily.get("temperature_2m_min") or [0])[0])
        rain = (daily.get("precipitation_probability_max") or [0])[0]
        summary = f"{now}°F {desc}, {lo}–{hi}°F, {rain}% rain · {location}"
        return Section(name=self.name, title=self.title, items=[SectionItem(title=summary)])
