"""
services/tineye_client.py — TinEye reverse image search API client.

TinEye API docs: https://api.tineye.com/documentation/
Searches billions of indexed images for exact and near-duplicate matches.
"""

import logging
from pathlib import Path

import requests

from config import Config
from core.models import ReverseSearchMatch

logger = logging.getLogger(__name__)

TINEYE_API_URL = "https://api.tineye.com/rest/search/"


class TinEyeClient:
    def search(self, image_path: str) -> list[ReverseSearchMatch]:
        """Upload image to TinEye and return match list."""
        path = Path(image_path)

        with open(path, "rb") as f:
            resp = requests.post(
                TINEYE_API_URL,
                files={"image": (path.name, f, "image/jpeg")},
                data={"api_key": Config.TINEYE_API_KEY},
                timeout=Config.REQUEST_TIMEOUT,
            )

        resp.raise_for_status()
        data = resp.json()

        matches = []
        for item in data.get("results", {}).get("matches", []):
            match = ReverseSearchMatch(
                service="TinEye",
                found=True,
                url=item.get("image_url", ""),
                page_title=item.get("domain", ""),
                first_seen_date=item.get("crawl_date", ""),
                similarity_score=item.get("score", None),
                match_type="exact" if item.get("score", 0) == 100 else "similar",
                thumbnail_url=item.get("thumbnail_url", ""),
            )
            matches.append(match)

        if not matches:
            matches.append(ReverseSearchMatch(service="TinEye", found=False))

        return matches
