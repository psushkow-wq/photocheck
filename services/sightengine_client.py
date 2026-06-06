"""
services/sightengine_client.py — Sightengine AI image detection.

API docs: https://sightengine.com/docs/check-if-image-is-ai-generated
Returns a 0–1 probability that the image is AI-generated.
"""

import logging
from pathlib import Path

import requests

from config import Config
from core.models import AIServiceResult

logger = logging.getLogger(__name__)

SIGHTENGINE_URL = "https://api.sightengine.com/1.0/check.json"


class SightengineClient:
    def detect(self, image_path: str) -> AIServiceResult:
        path = Path(image_path)

        with open(path, "rb") as f:
            resp = requests.post(
                SIGHTENGINE_URL,
                data={
                    "models": "genai",
                    "api_user": Config.SIGHTENGINE_API_USER,
                    "api_secret": Config.SIGHTENGINE_API_SECRET,
                },
                files={"media": (path.name, f)},
                timeout=Config.REQUEST_TIMEOUT,
            )

        resp.raise_for_status()
        data = resp.json()

        ai_prob = None
        verdict = "Нет данных"
        try:
            # Sightengine returns {"type": {"ai_generated": 0.98, "photo": 0.02}}
            type_data = data.get("type", {})
            ai_prob = float(type_data.get("ai_generated", 0))
            verdict = f"AI-generated: {ai_prob:.2%}, Photo: {type_data.get('photo', 0):.2%}"
        except Exception as e:
            logger.warning(f"Sightengine parse error: {e}")
            verdict = f"Ошибка парсинга: {e}"

        return AIServiceResult(
            service="Sightengine",
            ai_probability=ai_prob,
            verdict=verdict,
            details=data,
        )
