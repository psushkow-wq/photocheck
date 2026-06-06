"""
modules/forensics.py — Image forensics: ELA, JPEG analysis, manipulation heuristics.

Error Level Analysis (ELA) works only for JPEG images. It re-saves
the image at a known quality and computes the pixel-level difference
between the original and re-saved version. Regions that were edited
typically show higher error levels than undisturbed regions.

NOTE: ELA is a heuristic and can produce false positives (e.g. for images
saved at very low or very high quality). It is ONE indicator, not proof.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from core.models import ForensicsResult, ELAResult

logger = logging.getLogger(__name__)

# ELA re-save quality
ELA_QUALITY = 75
# Threshold above which a pixel difference is "suspicious"
ELA_DIFF_THRESHOLD = 10
# Percentage of pixels above threshold to flag as suspicious
ELA_SUSPICIOUS_THRESHOLD_PCT = 15.0


def run_forensics(image_path: str, workdir: str) -> ForensicsResult:
    result = ForensicsResult()
    path = Path(image_path)
    work = Path(workdir)

    # ── Basic file info ──────────────────────────────────────────────────────
    result.file_size_bytes = path.stat().st_size
    try:
        with Image.open(path) as img:
            result.width, result.height = img.size
            result.format = img.format or path.suffix.upper().lstrip(".")
            result.color_mode = img.mode
            result.has_alpha = img.mode in ("RGBA", "LA", "PA")
            result.color_profile = img.info.get("icc_profile") and "Присутствует" or "Отсутствует"

            # JPEG quality estimate
            if result.format in ("JPEG", "JPG"):
                result.jpeg_quality_estimate = _estimate_jpeg_quality(img)

    except Exception as e:
        logger.warning(f"Basic image info error: {e}")
        result.manipulation_flags.append(f"Ошибка чтения изображения: {e}")

    # ── ELA (JPEG only) ──────────────────────────────────────────────────────
    if result.format in ("JPEG", "JPG", ""):
        ela_path = work / "ela_result.jpg"
        try:
            result.ela = run_ela(str(path), str(ela_path))
        except Exception as e:
            logger.warning(f"ELA error: {e}")

    # ── OpenCV-based heuristics ──────────────────────────────────────────────
    try:
        _run_cv_heuristics(str(path), result)
    except Exception as e:
        logger.warning(f"CV heuristics error: {e}")

    # ── Compute manipulation score ───────────────────────────────────────────
    result.manipulation_score = _compute_manipulation_score(result)

    return result


def run_ela(image_path: str, output_path: str) -> ELAResult:
    """Run Error Level Analysis and save visualization."""
    ela_result = ELAResult()

    original = Image.open(image_path).convert("RGB")

    # Re-save at known quality
    resaved_path = output_path + "_resaved.jpg"
    original.save(resaved_path, "JPEG", quality=ELA_QUALITY)
    resaved = Image.open(resaved_path).convert("RGB")

    # Compute difference
    diff = ImageChops.difference(original, resaved)
    diff_array = np.array(diff, dtype=np.float32)

    ela_result.max_difference = float(np.max(diff_array))
    ela_result.mean_difference = float(np.mean(diff_array))

    # Amplify for visualization
    diff_array_vis = np.clip(diff_array * 15, 0, 255).astype(np.uint8)
    enhanced_diff = Image.fromarray(diff_array_vis)
    enhanced_diff.save(output_path, "JPEG", quality=90)
    ela_result.ela_image_path = output_path

    # Suspicious pixels
    gray_diff = np.mean(diff_array, axis=2)
    suspicious_pixels = np.sum(gray_diff > ELA_DIFF_THRESHOLD)
    total_pixels = gray_diff.size
    ela_result.suspicious_regions_percent = (suspicious_pixels / total_pixels) * 100

    if ela_result.suspicious_regions_percent > ELA_SUSPICIOUS_THRESHOLD_PCT:
        ela_result.notes.append(
            f"{ela_result.suspicious_regions_percent:.1f}% пикселей имеют "
            "повышенный уровень ошибки — возможно редактирование или пересохранение"
        )

    if ela_result.mean_difference > 5.0:
        ela_result.recompression_detected = True
        ela_result.notes.append(
            "Обнаружены признаки многократного пересохранения JPEG"
        )

    # Cleanup temp file
    try:
        os.remove(resaved_path)
    except Exception:
        pass

    return ela_result


def _run_cv_heuristics(image_path: str, result: ForensicsResult) -> None:
    """OpenCV-based noise and consistency analysis."""
    img = cv2.imread(image_path)
    if img is None:
        return

    # Noise analysis: very low noise in smooth areas can suggest AI generation
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if laplacian_var < 5:
        result.manipulation_flags.append(
            "Аномально низкая текстурная вариация (возможно AI-сглаживание)"
        )

    # Check for copy-move: simplified block-based check
    # (A real copy-move detector would use SIFT/ORB feature matching)
    # Placeholder — not implemented in MVP

    # DCT noise pattern (simplified)
    if result.format in ("JPEG", "JPG"):
        _check_dct_inconsistency(img, result)


def _check_dct_inconsistency(img: np.ndarray, result: ForensicsResult) -> None:
    """Check for inconsistent DCT block structure (very simplified)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    block_size = 8

    block_variances = []
    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = gray[y:y+block_size, x:x+block_size]
            dct_block = cv2.dct(block)
            block_variances.append(float(np.var(dct_block)))

    if block_variances:
        mean_var = np.mean(block_variances)
        std_var = np.std(block_variances)
        cv_ratio = std_var / (mean_var + 1e-9)
        if cv_ratio > 3.0:
            result.manipulation_flags.append(
                "Высокая неоднородность DCT-блоков — возможно вставка фрагментов с другим сжатием"
            )


def _estimate_jpeg_quality(img: Image.Image) -> Optional[int]:
    """Estimate JPEG save quality from quantization tables."""
    try:
        qt = img.quantization
        if qt and 0 in qt:
            # Standard luminance table baseline sum
            standard_sum = 65535
            actual_sum = sum(qt[0])
            quality = max(1, min(100, int(100 - (actual_sum / standard_sum) * 100)))
            return quality
    except Exception:
        pass
    return None


def _compute_manipulation_score(result: ForensicsResult) -> float:
    """0.0–1.0 manipulation suspicion based on forensic flags."""
    score = 0.0
    n_flags = len(result.manipulation_flags)

    if n_flags >= 3:
        score += 0.5
    elif n_flags >= 1:
        score += 0.2 * n_flags

    if result.ela:
        if result.ela.suspicious_regions_percent > 30:
            score += 0.3
        elif result.ela.suspicious_regions_percent > 15:
            score += 0.15
        if result.ela.recompression_detected:
            score += 0.1

    return min(score, 1.0)
