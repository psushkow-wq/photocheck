"""
core/risk_score.py — Calculates multi-dimensional risk scores from analysis results.

Produces a RiskScore with several independent dimensions rather than
one crude "fake percentage". Each dimension has its own logic.
"""

import logging
from core.models import (
    AnalysisResult, RiskScore, TrustLevel,
    MetadataResult, ForensicsResult, AIDetectionResult,
    ReverseSearchResult, AISuspicion
)

logger = logging.getLogger(__name__)


def compute_risk_score(result: AnalysisResult) -> RiskScore:
    """Build a RiskScore from all available sub-results."""
    score = RiskScore()
    red_flags = []
    auth_args = []
    checked = []
    skipped = []

    # ── 1. METADATA CONFIDENCE ──────────────────────────────────────────────
    if result.metadata:
        checked.append("Метаданные (EXIF/IPTC/XMP)")
        m: MetadataResult = result.metadata
        score.metadata_confidence_score = m.confidence_score

        if m.editing_software_detected:
            red_flags.append(f"Обнаружен тег редактирующего ПО: {m.editing_software_detected}")
        if m.thumbnail_mismatch:
            red_flags.append("Несоответствие thumbnail и основного изображения")
        if m.confidence_score == 0.0:
            red_flags.append("Метаданные полностью отсутствуют")
        elif m.confidence_score >= 0.6:
            auth_args.append("Метаданные присутствуют и содержат сведения об устройстве съёмки")

        if m.gps:
            score.geolocation_confidence_score = 0.9
            auth_args.append(f"Найдены GPS-координаты: {m.gps.latitude:.5f}, {m.gps.longitude:.5f}")
        else:
            skipped.append("Геолокация (GPS отсутствует)")
    else:
        skipped.append("Метаданные")

    # ── 2. FORENSICS / MANIPULATION ─────────────────────────────────────────
    if result.forensics:
        checked.append("Forensic-анализ изображения")
        f: ForensicsResult = result.forensics
        score.manipulation_suspicion_score = f.manipulation_score

        for flag in f.manipulation_flags:
            red_flags.append(flag)

        if f.ela and f.ela.suspicious_regions_percent > 20:
            red_flags.append(
                f"ELA: {f.ela.suspicious_regions_percent:.1f}% пикселей с подозрительным "
                "уровнем сжатия"
            )
        if f.manipulation_score < 0.2:
            auth_args.append("Forensic-анализ не выявил признаков монтажа")
    else:
        skipped.append("Forensic-анализ")

    # ── 3. AI DETECTION ─────────────────────────────────────────────────────
    if result.ai_detection:
        checked.append("AI-детекция")
        ai: AIDetectionResult = result.ai_detection
        score.ai_suspicion_score = ai.ai_suspicion_score

        if ai.overall_suspicion in (AISuspicion.STRONG, AISuspicion.MODERATE):
            red_flags.append(f"AI-анализ: {ai.overall_suspicion.value}")
        elif ai.overall_suspicion == AISuspicion.NONE:
            auth_args.append("AI-сервисы не обнаружили признаков генерации")

        for flag in ai.local_heuristics_flags:
            red_flags.append(f"Эвристика: {flag}")
    else:
        skipped.append("AI-детекция")

    # ── 4. REVERSE SEARCH ───────────────────────────────────────────────────
    if result.reverse_search:
        checked.append("Обратный поиск изображения")
        rs: ReverseSearchResult = result.reverse_search
        score.internet_provenance_score = rs.internet_provenance_score

        if rs.earliest_found_url:
            auth_args.append(
                f"Ранний источник: {rs.earliest_found_url} ({rs.earliest_found_date or 'дата неизвестна'})"
            )
        if rs.internet_provenance_score == 0.0 and rs.checked_services:
            auth_args.append("В интернете совпадений не найдено")
        for svc in rs.skipped_services:
            skipped.append(f"Обратный поиск через {svc}")
    else:
        skipped.append("Обратный поиск")

    # ── 5. OVERALL TRUST LEVEL ──────────────────────────────────────────────
    score.red_flags = red_flags
    score.authenticity_arguments = auth_args
    score.what_was_checked = checked
    score.what_was_skipped = skipped

    score.overall_trust_level = _compute_trust_level(score)
    score.overall_summary = _build_summary(score)

    return score


def _compute_trust_level(score: RiskScore) -> TrustLevel:
    """
    Heuristic trust-level calculation.
    No single number can capture authenticity — this is a rough guide only.
    """
    n_flags = len(score.red_flags)

    high_risk = (
        score.ai_suspicion_score > 0.65
        or score.manipulation_suspicion_score > 0.65
    )
    moderate_risk = (
        score.ai_suspicion_score > 0.35
        or score.manipulation_suspicion_score > 0.35
        or score.metadata_confidence_score < 0.2
        or n_flags >= 2
    )

    if score.what_was_checked == []:
        return TrustLevel.UNKNOWN
    if high_risk or n_flags >= 3:
        return TrustLevel.LOW
    if moderate_risk:
        return TrustLevel.MEDIUM
    return TrustLevel.HIGH


def _build_summary(score: RiskScore) -> str:
    trust_labels = {
        TrustLevel.HIGH: "Высокий уровень доверия",
        TrustLevel.MEDIUM: "Средний уровень доверия",
        TrustLevel.LOW: "Низкий уровень доверия — выявлены подозрительные признаки",
        TrustLevel.UNKNOWN: "Уровень доверия не определён",
    }
    label = trust_labels[score.overall_trust_level]

    parts = [
        f"Итоговая оценка: {label}.",
        "",
        "⚠️ Важно: это не судебная экспертиза, а предварительный OSINT/forensic-анализ.",
        "Результат носит вероятностный характер и не является доказательством подлинности или фальсификации.",
    ]

    if score.red_flags:
        parts.append("\nОбнаруженные признаки, вызывающие сомнение:")
        for flag in score.red_flags:
            parts.append(f"  • {flag}")

    if score.authenticity_arguments:
        parts.append("\nАргументы в пользу подлинности:")
        for arg in score.authenticity_arguments:
            parts.append(f"  • {arg}")

    return "\n".join(parts)
