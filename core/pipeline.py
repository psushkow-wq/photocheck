"""
core/pipeline.py — Main analysis pipeline.

Orchestrates all modules in sequence, emitting progress callbacks
so the UI can update in real time. Runs in a background thread.
"""

import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

from config import Config
from core.models import AnalysisResult
from core.risk_score import compute_risk_score
from modules.metadata_extractor import extract_metadata
from modules.hashing import compute_hashes
from modules.forensics import run_forensics
from modules.ai_detection import run_ai_detection
from modules.reverse_search import run_reverse_search
from data.database import save_result_to_db

logger = logging.getLogger(__name__)


def run_pipeline(
    image_path: str,
    mode: str = "fast",
    allow_external: bool = False,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> AnalysisResult:
    """
    Execute the full analysis pipeline.

    Args:
        image_path: Path to the image file to analyse.
        mode: 'fast' | 'full' | 'local'
        allow_external: Whether to send the image to external APIs.
        progress_callback: Called with (message: str, fraction: float) during analysis.
    Returns:
        AnalysisResult with all sub-results filled in.
    """

    def progress(msg: str, frac: float) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg, frac)

    result = AnalysisResult(
        image_path=image_path,
        analysis_id=str(uuid.uuid4()),
        mode=mode,
    )

    # ── Step 1: Validate file ────────────────────────────────────────────────
    progress("Проверяю файл...", 0.02)
    src = Path(image_path)
    if not src.exists():
        result.errors.append(f"Файл не найден: {image_path}")
        return result

    suffix = src.suffix.lower()
    if suffix not in Config.SUPPORTED_FORMATS:
        result.errors.append(f"Неподдерживаемый формат: {suffix}")
        return result

    size_mb = src.stat().st_size / (1024 * 1024)
    if size_mb > 50:
        result.errors.append(f"Файл слишком большой: {size_mb:.1f} МБ (максимум 50 МБ)")
        return result

    # ── Step 2: Safe working copy ────────────────────────────────────────────
    progress("Создаю рабочую копию...", 0.05)
    workdir = Path(tempfile.mkdtemp(prefix="photo_auth_"))
    work_copy = workdir / src.name
    shutil.copy2(src, work_copy)
    result.log_entries.append(f"Рабочая копия: {work_copy}")

    try:
        # ── Step 3: Metadata ─────────────────────────────────────────────────
        progress("Читаю метаданные (EXIF/IPTC/XMP)...", 0.10)
        try:
            result.metadata = extract_metadata(str(work_copy))
            result.log_entries.append("Метаданные извлечены")
        except Exception as e:
            result.errors.append(f"Ошибка извлечения метаданных: {e}")
            logger.exception("Metadata extraction failed")

        # ── Step 4: Hashing ──────────────────────────────────────────────────
        progress("Вычисляю хэши изображения...", 0.18)
        try:
            result.hashes = compute_hashes(str(work_copy))
            result.log_entries.append("Хэши вычислены")
        except Exception as e:
            result.errors.append(f"Ошибка вычисления хэшей: {e}")
            logger.exception("Hashing failed")

        # ── Step 5: Forensics ────────────────────────────────────────────────
        progress("Провожу forensic-анализ...", 0.28)
        try:
            result.forensics = run_forensics(str(work_copy), str(workdir))
            result.log_entries.append("Forensic-анализ завершён")
        except Exception as e:
            result.errors.append(f"Ошибка forensic-анализа: {e}")
            logger.exception("Forensics failed")

        # ── Step 6: AI detection (local heuristics always; APIs if allowed) ──
        progress("Анализирую признаки AI-генерации...", 0.45)
        try:
            result.ai_detection = run_ai_detection(
                str(work_copy),
                allow_external=(allow_external and mode != "local"),
            )
            result.log_entries.append("AI-анализ завершён")
        except Exception as e:
            result.errors.append(f"Ошибка AI-анализа: {e}")
            logger.exception("AI detection failed")

        # ── Step 7: Reverse image search ─────────────────────────────────────
        if mode != "local" and allow_external:
            progress("Выполняю обратный поиск изображения...", 0.62)
            try:
                result.reverse_search = run_reverse_search(str(work_copy))
                result.log_entries.append("Обратный поиск завершён")
            except Exception as e:
                result.errors.append(f"Ошибка обратного поиска: {e}")
                logger.exception("Reverse search failed")
        else:
            result.log_entries.append(
                "Обратный поиск пропущен (режим local или внешние запросы запрещены)"
            )

        # ── Step 8: Risk scoring ──────────────────────────────────────────────
        progress("Формирую оценку достоверности...", 0.85)
        try:
            result.risk_score = compute_risk_score(result)
            result.log_entries.append("Оценка рисков вычислена")
        except Exception as e:
            result.errors.append(f"Ошибка вычисления рисков: {e}")
            logger.exception("Risk scoring failed")

        # ── Step 9: Save to DB ────────────────────────────────────────────────
        progress("Сохраняю в историю...", 0.93)
        try:
            save_result_to_db(result)
        except Exception as e:
            logger.warning(f"DB save failed (non-critical): {e}")

        result.completed = True
        progress("Анализ завершён ✓", 1.0)

    finally:
        # Keep workdir — forensics images (ELA) are referenced by path.
        # A production app would manage cleanup with a TTL cache.
        pass

    return result
