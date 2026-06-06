"""
modules/ai_detection.py — Orchestrates AI-generated image detection.

Runs local heuristics always.
Calls external APIs only when allow_external=True and keys are configured.
"""

import logging

from config import Config
from core.models import AIDetectionResult, AIServiceResult, AISuspicion
from services.hive_client import HiveClient
from services.sightengine_client import SightengineClient
from services.illuminarty_client import IlluminartyClient

logger = logging.getLogger(__name__)


def run_ai_detection(image_path: str, allow_external: bool = False) -> AIDetectionResult:
    result = AIDetectionResult()

    # ── Local heuristics (always run) ───────────────────────────────────────
    _run_local_heuristics(image_path, result)

    if not allow_external:
        result.overall_suspicion = _summarise(result)
        return result

    # ── External APIs ────────────────────────────────────────────────────────
    if Config.has_hive():
        try:
            r = HiveClient().detect(image_path)
            result.service_results.append(r)
        except Exception as e:
            result.service_results.append(AIServiceResult(service="Hive", error=str(e)))

    if Config.has_sightengine():
        try:
            r = SightengineClient().detect(image_path)
            result.service_results.append(r)
        except Exception as e:
            result.service_results.append(AIServiceResult(service="Sightengine", error=str(e)))

    if Config.has_illuminarty():
        try:
            r = IlluminartyClient().detect(image_path)
            result.service_results.append(r)
        except Exception as e:
            result.service_results.append(AIServiceResult(service="Illuminarty", error=str(e)))

    # ── Aggregate ────────────────────────────────────────────────────────────
    result.overall_suspicion = _summarise(result)
    result.ai_suspicion_score = _compute_score(result)

    return result


def _run_local_heuristics(image_path: str, result: AIDetectionResult) -> None:
    """
    Simple heuristics that suggest AI generation.
    These are soft signals, not proof.
    """
    import cv2
    import numpy as np
    from PIL import Image

    flags = []

    try:
        img = cv2.imread(image_path)
        if img is None:
            return

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Texture uniformity (AI images often have unnaturally smooth skin/backgrounds)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap_var < 50:
            flags.append("Необычно равномерная текстура — характерна для AI-генерации")

        # 2. High-frequency noise analysis
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        noise = gray.astype(float) - blur.astype(float)
        noise_std = np.std(noise)
        if noise_std < 1.5:
            flags.append("Очень низкий уровень шума — возможна AI-генерация")

        # 3. Color distribution check (AI images often have unusual color histograms)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sat_std = np.std(hsv[:, :, 1])
        if sat_std < 10:
            flags.append("Необычно однородная насыщенность — возможна AI-генерация")

        # 4. Check for typical AI-generated background blur patterns
        # (simplified — real version would use segmentation)

    except Exception as e:
        logger.debug(f"Local heuristics error: {e}")

    # 5. Check for absence of EXIF — not proof but worth flagging
    try:
        from PIL import Image as PILImage
        with PILImage.open(image_path) as pil_img:
            exif = pil_img._getexif()
            if exif is None:
                flags.append(
                    "Метаданные отсутствуют — соцсети и мессенджеры удаляют EXIF, "
                    "но генераторы также не создают метаданных"
                )
    except Exception:
        pass

    result.local_heuristics_flags = flags


def _summarise(result: AIDetectionResult) -> AISuspicion:
    """Aggregate service verdicts into a single suspicion level."""
    if not result.service_results and not result.local_heuristics_flags:
        return AISuspicion.INSUFFICIENT

    if not result.service_results:
        # Only local heuristics
        if len(result.local_heuristics_flags) >= 3:
            return AISuspicion.WEAK
        return AISuspicion.INSUFFICIENT

    scores = [r.ai_probability for r in result.service_results if r.ai_probability is not None]
    errors = [r for r in result.service_results if r.error]

    if not scores:
        if len(errors) == len(result.service_results):
            return AISuspicion.INSUFFICIENT
        return AISuspicion.INSUFFICIENT

    avg = sum(scores) / len(scores)

    if len(scores) > 1:
        max_diff = max(scores) - min(scores)
        if max_diff > 0.4:
            return AISuspicion.CONTRADICTORY

    if avg >= 0.7:
        return AISuspicion.STRONG
    if avg >= 0.4:
        return AISuspicion.MODERATE
    if avg >= 0.15:
        return AISuspicion.WEAK
    return AISuspicion.NONE


def _compute_score(result: AIDetectionResult) -> float:
    scores = [r.ai_probability for r in result.service_results if r.ai_probability is not None]
    if not scores:
        return 0.1 * len(result.local_heuristics_flags)
    return sum(scores) / len(scores)
