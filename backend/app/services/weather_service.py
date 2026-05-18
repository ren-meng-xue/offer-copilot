import logging
from dataclasses import dataclass, field

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"


@dataclass
class LiveWeather:
    city: str
    weather: str
    temperature: str
    wind_direction: str
    wind_power: str
    humidity: str


@dataclass
class DayForecast:
    date: str
    day_weather: str
    night_weather: str
    day_temp: str
    night_temp: str
    day_wind: str
    day_power: str


@dataclass
class WeatherData:
    city: str
    live: LiveWeather
    forecast: list[DayForecast] = field(default_factory=list)


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """坐标 → 高德 adcode（6 位区划码）。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AMAP_BASE}/geocode/regeo",
                params={
                    "key": settings.AMAP_API_KEY,
                    "location": f"{lng},{lat}",
                    "extensions": "base",
                },
            )
            data = resp.json()
            if data.get("status") != "1":
                return None
            return data["regeocode"]["addressComponent"]["adcode"] or None
    except Exception as exc:
        logger.warning("reverse_geocode failed: %s", exc)
        return None


async def geocode_city(city_name: str) -> str | None:
    """城市名 → 高德 adcode。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AMAP_BASE}/geocode/geo",
                params={"key": settings.AMAP_API_KEY, "address": city_name},
            )
            data = resp.json()
            if data.get("status") != "1" or not data.get("geocodes"):
                return None
            return data["geocodes"][0]["adcode"] or None
    except Exception as exc:
        logger.warning("geocode_city failed: %s", exc)
        return None


async def fetch_weather(adcode: str) -> WeatherData | None:
    """查询实况 + 预报。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            live_resp, forecast_resp = await _fetch_both(client, adcode)

        live_data = live_resp.json()
        forecast_data = forecast_resp.json()

        if live_data.get("status") != "1" or not live_data.get("lives"):
            return None

        live_raw = live_data["lives"][0]
        live = LiveWeather(
            city=live_raw.get("city", ""),
            weather=live_raw.get("weather", ""),
            temperature=live_raw.get("temperature", ""),
            wind_direction=live_raw.get("winddirection", ""),
            wind_power=live_raw.get("windpower", ""),
            humidity=live_raw.get("humidity", ""),
        )

        forecast: list[DayForecast] = []
        if forecast_data.get("status") == "1" and forecast_data.get("forecasts"):
            for cast in forecast_data["forecasts"][0].get("casts", []):
                forecast.append(
                    DayForecast(
                        date=cast.get("date", ""),
                        day_weather=cast.get("dayweather", ""),
                        night_weather=cast.get("nightweather", ""),
                        day_temp=cast.get("daytemp", ""),
                        night_temp=cast.get("nighttemp", ""),
                        day_wind=cast.get("daywind", ""),
                        day_power=cast.get("daypower", ""),
                    )
                )

        return WeatherData(city=live.city, live=live, forecast=forecast)
    except Exception as exc:
        logger.warning("fetch_weather failed: %s", exc)
        return None


async def _fetch_both(
    client: httpx.AsyncClient, adcode: str
) -> tuple[httpx.Response, httpx.Response]:
    import asyncio

    live_task = client.get(
        f"{AMAP_BASE}/weather/weatherInfo",
        params={"key": settings.AMAP_API_KEY, "city": adcode, "extensions": "base"},
    )
    forecast_task = client.get(
        f"{AMAP_BASE}/weather/weatherInfo",
        params={"key": settings.AMAP_API_KEY, "city": adcode, "extensions": "all"},
    )
    return await asyncio.gather(live_task, forecast_task)
