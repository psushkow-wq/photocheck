"""
services/hive_client.py — Hive Moderation AI-generated image detection.

API docs: https://docs.thehive.ai/docs/ai-generated-content-detection
Returns a probability that an image is AI-generated.
"""

import logging
from pathlib import Path

import requests

from config import Config
from core.models import AIServiceResult

logger = logging.getLogger(__name__)

HIVE_AI_GENERATED_URL = "https://api.thehive.ai/api/v2/task/sync"


class HiveClient:
    def detect(self, image_path: str) -> AIServiceResult:
        path = Path(image_path)

        with open(path, "rb") as f:
            resp = requests.post(
                HIVE_AI_GENERATED_URL,
                headers={"Authorization": f"Token {Config.HIVE_API_KEY}"},
                files={"image": (path.name, f, "image/jpeg")},
                timeout=Config.REQUEST_TIMEOUT,
            )

        resp.raise_for_status()
        data = resp.json()

        # Parse Hive response structure
        ai_prob = None
        verdict = "Нет данных"
        try:
            output = data["status"][0]["response"]["output"][0]
            classes = output.get("classes", [])
            for cls in classes:
                if cls.get("class") == "ai_generated":
                    ai_prob = float(cls["score"])
                    verdict = f"AI-generated score: {ai_prob:.2%}"
                    break
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Hive response parse error: {e}")
            verdict = f"Ошибка парсинга ответа: {e}"

        return AIServiceResult(
            service="Hive AI Detection",
            ai_probability=ai_prob,
            verdict=verdict,
            details=data,
        )
