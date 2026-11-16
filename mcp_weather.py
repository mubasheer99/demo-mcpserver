"""MCP server for current weather and forecasts from Open-Meteo."""

from datetime import datetime, timedelta, timezone
from typing import Literal

import requests
from mcp.server.fastmcp import FastMCP

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
REQUEST_TIMEOUT_SECONDS = 30

Units = Literal["standard", "metric", "imperial"]

mcp = FastMCP("open-meteo-weather-server")


def _validate_city(city: str) -> str:
    cleaned = city.strip()
    if not cleaned:
        raise ValueError("city must not be empty.")
    return cleaned


def _validate_units(units: Units) -> Units:
    if units not in {"standard", "metric", "imperial"}:
        raise ValueError("units must be one of: standard, metric, imperial.")
    return units


def _validate_days(days: int) -> int:
    if not 1 <= days <= 5:
        raise ValueError("days must be between 1 and 5.")
    return days


def _request_json(url: str, params: dict[str, str | int | float]) -> dict:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        detail = error.response.text if error.response is not None else ""
        raise RuntimeError(
            f"Open-Meteo API returned HTTP {status}. "
            f"{detail.strip() or 'Check the location and API request parameters.'}"
        ) from None
    except requests.RequestException as error:
        raise RuntimeError(f"Unable to reach Open-Meteo API ({type(error).__name__}).") from None
    except ValueError as error:
        raise RuntimeError("Open-Meteo API returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise RuntimeError("Open-Meteo returned an unexpected response.")
    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo error: {payload.get('reason', 'Unknown API error.')}")
    return payload


def _resolve_location(city: str, country: str | None) -> dict:
    params: dict[str, str | int] = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    query = city
    country_name = country.strip() if country else ""
    if len(country_name) == 2 and country_name.isalpha():
        params["countryCode"] = country_name.upper()
    elif country_name:
        query = f"{city},{country_name}"
        params["name"] = query
    payload = _request_json(
        GEOCODING_URL,
        params,
    )
    locations = payload.get("results", [])
    if not isinstance(locations, list):
        raise RuntimeError("Open-Meteo returned an unexpected geocoding response.")
    if not locations:
        raise ValueError(f"No Open-Meteo location found for '{query}'.")

    location = locations[0]
    if (
        not isinstance(location, dict)
        or not isinstance(location.get("latitude"), (int, float))
        or not isinstance(location.get("longitude"), (int, float))
    ):
        raise RuntimeError("Open-Meteo returned an invalid geocoding result.")
    return location


def _request_units(units: Units) -> dict[str, str]:
    if units == "imperial":
        return {
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        }
    return {"wind_speed_unit": "ms", "precipitation_unit": "mm"}


def _convert_temperature(value: float | int | None, units: Units) -> float | int | None:
    if value is not None and units == "standard":
        return value + 273.15
    return value


def _weather(code: int | None) -> dict:
    conditions = {
        0: ("Clear", "clear sky"),
        1: ("Clear", "mainly clear"),
        2: ("Clouds", "partly cloudy"),
        3: ("Clouds", "overcast"),
        45: ("Fog", "fog"),
        48: ("Fog", "depositing rime fog"),
        51: ("Drizzle", "light drizzle"),
        53: ("Drizzle", "moderate drizzle"),
        55: ("Drizzle", "dense drizzle"),
        56: ("Drizzle", "light freezing drizzle"),
        57: ("Drizzle", "dense freezing drizzle"),
        61: ("Rain", "slight rain"),
        63: ("Rain", "moderate rain"),
        65: ("Rain", "heavy rain"),
        66: ("Rain", "light freezing rain"),
        67: ("Rain", "heavy freezing rain"),
        71: ("Snow", "slight snowfall"),
        73: ("Snow", "moderate snowfall"),
        75: ("Snow", "heavy snowfall"),
        77: ("Snow", "snow grains"),
        80: ("Rain", "slight rain showers"),
        81: ("Rain", "moderate rain showers"),
        82: ("Rain", "violent rain showers"),
        85: ("Snow", "slight snow showers"),
        86: ("Snow", "heavy snow showers"),
        95: ("Thunderstorm", "thunderstorm"),
        96: ("Thunderstorm", "thunderstorm with slight hail"),
        99: ("Thunderstorm", "thunderstorm with heavy hail"),
    }
    summary, description = conditions.get(code, ("Unknown", "unknown conditions"))
    return {"summary": summary, "description": description, "icon": None}


def _timestamp(local_time: str, utc_offset_seconds: int) -> int:
    try:
        value = datetime.fromisoformat(local_time)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone(timedelta(seconds=utc_offset_seconds)))
        return int(value.timestamp())
    except (OverflowError, OSError, TypeError, ValueError) as error:
        raise RuntimeError("Open-Meteo returned an invalid date or timezone offset.") from error


def _daily_value(daily: dict, key: str, index: int = 0):
    values = daily.get(key)
    if not isinstance(values, list) or len(values) <= index:
        raise RuntimeError("Open-Meteo returned an incomplete daily weather response.")
    return values[index]


def _forecast_params(location: dict, units: Units, days: int) -> dict[str, str | int | float]:
    return {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,"
            "pressure_msl,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,"
            "wind_gusts_10m,uv_index,precipitation,weather_code"
        ),
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
            "sunrise,sunset,uv_index_max,precipitation_probability_max,wind_speed_10m_max,"
            "wind_direction_10m_dominant,wind_gusts_10m_max"
        ),
        "forecast_days": days,
        "timezone": "auto",
        **_request_units(units),
    }


def _normalize_forecast_item(daily: dict, index: int, units: Units, offset: int) -> dict:
    return {
        "timestamp": _timestamp(_daily_value(daily, "time", index) + "T12:00", offset),
        "date": _daily_value(daily, "time", index),
        "weather": _weather(_daily_value(daily, "weather_code", index)),
        "temperature": {
            "current": _convert_temperature(_daily_value(daily, "temperature_2m_max", index), units),
            "feels_like": _convert_temperature(
                _daily_value(daily, "apparent_temperature_max", index), units
            ),
            "min": _convert_temperature(_daily_value(daily, "temperature_2m_min", index), units),
            "max": _convert_temperature(_daily_value(daily, "temperature_2m_max", index), units),
            "morning": None,
            "day": _convert_temperature(_daily_value(daily, "temperature_2m_max", index), units),
            "evening": None,
            "night": None,
            "units": units,
        },
        "humidity": None,
        "pressure": None,
        "wind": {
            "speed": _daily_value(daily, "wind_speed_10m_max", index),
            "deg": _daily_value(daily, "wind_direction_10m_dominant", index),
            "gust": _daily_value(daily, "wind_gusts_10m_max", index),
        },
        "clouds": None,
        "pop": _daily_value(daily, "precipitation_probability_max", index),
        "sunrise": _timestamp(_daily_value(daily, "sunrise", index), offset),
        "sunset": _timestamp(_daily_value(daily, "sunset", index), offset),
        "uvi": _daily_value(daily, "uv_index_max", index),
    }


@mcp.tool()
def get_current_weather(city: str, units: Units = "metric", country: str | None = None) -> dict:
    """Get current weather for a city using the free Open-Meteo API."""
    city_name = _validate_city(city)
    units = _validate_units(units)
    location = _resolve_location(city_name, country)
    payload = _request_json(FORECAST_URL, _forecast_params(location, units, 1))

    current = payload.get("current")
    daily = payload.get("daily")
    offset = payload.get("utc_offset_seconds")
    if not isinstance(current, dict) or not isinstance(daily, dict) or not isinstance(offset, int):
        raise RuntimeError("Open-Meteo returned an unexpected current weather response.")

    current_time = current.get("time")
    if not isinstance(current_time, str):
        raise RuntimeError("Open-Meteo returned an invalid current weather time.")
    date = current_time[:10]
    dates = daily.get("time")
    if not isinstance(dates, list) or date not in dates:
        raise RuntimeError("Open-Meteo returned no daily weather for the current date.")
    day_index = dates.index(date)

    return {
        "city": location.get("name"),
        "country": location.get("country_code"),
        "coordinates": {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
        },
        "weather": _weather(current.get("weather_code")),
        "temperature": {
            "current": _convert_temperature(current.get("temperature_2m"), units),
            "feels_like": _convert_temperature(current.get("apparent_temperature"), units),
            "min": _convert_temperature(_daily_value(daily, "temperature_2m_min", day_index), units),
            "max": _convert_temperature(_daily_value(daily, "temperature_2m_max", day_index), units),
            "units": units,
        },
        "humidity": current.get("relative_humidity_2m"),
        "pressure": current.get("pressure_msl"),
        "wind": {
            "speed": current.get("wind_speed_10m"),
            "deg": current.get("wind_direction_10m"),
            "gust": current.get("wind_gusts_10m"),
        },
        "clouds": current.get("cloud_cover"),
        "visibility": current.get("visibility"),
        "sunrise": _timestamp(_daily_value(daily, "sunrise", day_index), offset),
        "sunset": _timestamp(_daily_value(daily, "sunset", day_index), offset),
        "dew_point": _convert_temperature(current.get("dew_point_2m"), units),
        "uvi": current.get("uv_index"),
        "timestamp": _timestamp(current_time, offset),
        "timezone": payload.get("timezone"),
        "units": units,
    }


@mcp.tool()
def get_weather_forecast(
    city: str,
    days: int = 3,
    units: Units = "metric",
    country: str | None = None,
) -> dict:
    """Get a daily weather forecast using the free Open-Meteo API."""
    city_name = _validate_city(city)
    days = _validate_days(days)
    units = _validate_units(units)
    location = _resolve_location(city_name, country)
    payload = _request_json(FORECAST_URL, _forecast_params(location, units, days))

    daily = payload.get("daily")
    offset = payload.get("utc_offset_seconds")
    if not isinstance(daily, dict) or not isinstance(offset, int):
        raise RuntimeError("Open-Meteo returned an unexpected daily forecast response.")
    dates = daily.get("time")
    if not isinstance(dates, list) or not all(isinstance(date, str) for date in dates):
        raise RuntimeError("Open-Meteo returned an unexpected daily forecast response.")

    return {
        "city": location.get("name"),
        "country": location.get("country_code"),
        "coordinates": {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
        },
        "units": units,
        "forecast": [
            _normalize_forecast_item(daily, index, units, offset)
            for index in range(min(days, len(dates)))
        ],
    }



