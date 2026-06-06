"""
modules/reverse_search.py — Orchestrates reverse image search across services.

Each service client is tried independently; failures don't abort others.
Manual fallback URLs are generated for services without API access.
"""

import logging
import webbrowser
from pathlib import Path

from config import Config
from core.models import ReverseSearchResult, ReverseSearchMatch
from services.tineye_client import TinEyeClient
from services.serpapi_client import SerpApiClient
from services.bing_client import BingClient

logger = logging.getLogger(__name__)


def run_reverse_search(image_path: str) -> ReverseSearchResult:
    result = ReverseSearchResult()

    # ── TinEye ───────────────────────────────────────────────────────────────
    if Config.has_tineye():
        try:
            matches = TinEyeClient().search(image_path)
            result.matches.extend(matches)
            result.checked_services.append("TinEye")
        except Exception as e:
            result.matches.append(ReverseSearchMatch(service="TinEye", error=str(e)))
            logger.warning(f"TinEye error: {e}")
    else:
        result.skipped_services.append("TinEye (API-ключ не задан)")
        _add_manual_fallback(result, "TinEye", "https://tineye.com/")

    # ── SerpAPI (Google Lens + Yandex) ───────────────────────────────────────
    if Config.has_serpapi():
        try:
            matches = SerpApiClient().search(image_path)
            result.matches.extend(matches)
            result.checked_services.append("SerpAPI")
        except Exception as e:
            result.matches.append(ReverseSearchMatch(service="SerpAPI", error=str(e)))
            logger.warning(f"SerpAPI error: {e}")
    else:
        result.skipped_services.append("SerpAPI (ключ не задан)")
        _add_manual_fallback(result, "Google Images (ручной)", "https://images.google.com/")
        
    # ── Bing Visual Search ────────────────────────────────────────────────────
    if Config.has_bing():
        try:
            matches = BingClient().search(image_path)
            result.matches.extend(matches)
            result.checked_services.append("Bing Visual Search")
        except Exception as e:
            result.matches.append(ReverseSearchMatch(service="Bing", error=str(e)))
            logger.warning(f"Bing error: {e}")
    else:
        result.skipped_services.append("Bing Visual Search (ключ не задан)")

    # ── Compute provenance score ──────────────────────────────────────────────
    found_matches = [m for m in result.matches if m.found and not m.error]
    if found_matches:
        result.internet_provenance_score = min(1.0, len(found_matches) * 0.3)
        # Find earliest date
        dates = [m.first_seen_date for m in found_matches if m.first_seen_date]
        if dates:
            result.earliest_found_date = min(dates)
            # Find corresponding URL
            earliest_match = next(
                (m for m in found_matches if m.first_seen_date == result.earliest_found_date), None
            )
            if earliest_match:
                result.earliest_found_url = earliest_match.url

    return result


def open_manual_search(service_url: str) -> None:
    """Open browser for manual reverse image search."""
    webbrowser.open(service_url)


def _add_manual_fallback(
    result: ReverseSearchResult, service_name: str, url: str
) -> None:
    result.matches.append(ReverseSearchMatch(
        service=service_name,
        found=False,
        url=url,
        match_type="manual_fallback",
        error=None,
    ))
