"""
modules/geolocation.py — Reverse geocoding: GPS coordinates → address.

Uses OpenCage Geocoder API (free tier: 2500 req/day).
Falls back to OpenStreetMap Nominatim (no key required, but rate-limited).
"""

import logging
import time

import requests

from config import Config
from core.models import GPSInfo

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
OPENCAGE_URL = "https://api.opencagedata.com/geocode/v1/json"


def reverse_geocode(gps: GPSInfo) -> str:
    """Return a human-readable address for GPS coordinates."""
    if Config.has_opencage():
        try:
            return _opencage(gps.latitude, gps.longitude)
        except Exception as e:
            logger.warning(f"OpenCage error: {e}")

    # Fallback: Nominatim (respect 1 req/sec rate limit)
    try:
        return _nominatim(gps.latitude, gps.longitude)
    except Exception as e:
        logger.warning(f"Nominatim error: {e}")
        return "Не удалось определить адрес"


def _opencage(lat: float, lon: float) -> str:
    resp = requests.get(
        OPENCAGE_URL,
        params={
            "q": f"{lat},{lon}",
            "key": Config.OPENCAGE_API_KEY,
            "language": "ru",
            "limit": 1,
        },
        timeout=Config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if results:
        return results[0].get("formatted", "")
    return "Адрес не найден"


def _nominatim(lat: float, lon: float) -> str:
    time.sleep(1)  # Rate limit courtesy
    resp = requests.get(
        NOMINATIM_URL,
        params={"lat": lat, "lon": lon, "format": "json", "accept-language": "ru"},
        headers={"User-Agent": "PhotoAuthenticator/1.0"},
        timeout=Config.REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("display_name", "Адрес не найден")
