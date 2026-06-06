"""
services/serpapi_client.py — SerpAPI client for Google Lens reverse image search.
Uses freeimage.host to get a public URL for the image.
"""

import base64
import logging
from io import BytesIO

import requests

from config import Config
from core.models import ReverseSearchMatch

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"
FREEIMAGE_UPLOAD_URL = "https://freeimage.host/api/1/upload"
FREEIMAGE_KEY = "6d207e02198a847aa98d0a2a901485a5"


class SerpApiClient:
    def search(self, image_path: str) -> list[ReverseSearchMatch]:
        public_url = self._upload_image(image_path)
        if not public_url:
            return [ReverseSearchMatch(
                service="Google Lens (SerpAPI)",
                error="Не удалось загрузить фото на freeimage.host"
            )]
        return self._google_lens(public_url)

    def _upload_image(self, image_path: str) -> str | None:
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img.thumbnail((1024, 1024))
                buf = BytesIO()
                img.convert("RGB").save(buf, "JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode()

            resp = requests.post(
                FREEIMAGE_UPLOAD_URL,
                params={"key": FREEIMAGE_KEY},
                data={"source": b64, "format": "json"},
                timeout=30,
            )
            resp.raise_for_status()
            url = resp.json()["image"]["url"]
            logger.info(f"Изображение загружено: {url}")
            return url
        except Exception as e:
            logger.warning(f"Ошибка загрузки на freeimage.host: {e}")
            return None

    def _google_lens(self, image_url: str) -> list[ReverseSearchMatch]:
        try:
            resp = requests.get(
                SERPAPI_BASE,
                params={
                    "engine": "google_lens",
                    "url": image_url,
                    "api_key": Config.SERPAPI_KEY,
                },
                timeout=Config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return [ReverseSearchMatch(service="Google Lens (SerpAPI)", error=data["error"])]

            matches = []
            for item in data.get("visual_matches", []):
                matches.append(ReverseSearchMatch(
                    service="Google Lens (SerpAPI)",
                    found=True,
                    url=item.get("link", ""),
                    page_title=item.get("title", ""),
                    thumbnail_url=item.get("thumbnail", ""),
                    match_type="visual",
                    similarity_score=(1.0 / item["position"]) if item.get("position") else None,
                ))

            if not matches:
                return [ReverseSearchMatch(service="Google Lens (SerpAPI)", found=False)]
            return matches

        except Exception as e:
            logger.warning(f"Google Lens SerpAPI error: {e}")
            return [ReverseSearchMatch(service="Google Lens (SerpAPI)", error=str(e))]
