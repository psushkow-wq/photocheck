"""
services/illuminarty_client.py — Illuminarty AI image detection.

API docs: https://illuminarty.ai/en/api.html
Returns probability + detected generator type if AI-generated.
"""

import logging
from pathlib import Path

import requests

from config import Config
from core.models import AIServiceResult

logger = logging.getLogger(__name__)

ILLUMINARTY_URL = "https://api.illuminarty.ai/v1/identify"


class IlluminartyClient:
    def detect(self, image_path: str) -> AIServiceResult:
        path = Path(image_path)

        with open(path, "rb") as f:
            resp = requests.post(
                ILLUMINARTY_URL,
                headers={"Authorization": f"Bearer {Config.ILLUMINARTY_API_KEY}"},
                files={"image": (path.name, f)},
                timeout=Config.REQUEST_TIMEOUT,
            )

        resp.raise_for_status()
        data = resp.json()

        ai_prob = None
        verdict = "Нет данных"
        try:
            ai_prob = float(data.get("ai_score", data.get("probability", 0)))
            generator = data.get("generator", data.get("model", ""))
            verdict = f"AI score: {ai_prob:.2%}"
            if generator:
                verdict += f" (предполагаемый генератор: {generator})"
        except Exception as e:
            logger.warning(f"Illuminarty parse error: {e}")
            verdict = f"Ошибка парсинга: {e}"

        return AIServiceResult(
            service="Illuminarty",
            ai_probability=ai_prob,
            verdict=verdict,
            details=data,
        )
