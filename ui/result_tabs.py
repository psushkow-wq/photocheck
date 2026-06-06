"""
Патч для result_tabs.py — исправляет зависание при переходе на вкладки Интернет и AI.

Изменения:
1. Длинные строки ошибок обрезаются до разумной длины
2. Добавлен wraplength для текстов
3. Вкладки строятся лениво (только при первом открытии)
"""

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from core.models import AnalysisResult, TrustLevel, AISuspicion
from modules.report_generator import (
    build_short_summary,
    generate_html_report,
    generate_json_report,
)

DARK_BG    = "#0f1117"
CARD_BG    = "#1a1d27"
BORDER     = "#2d3148"
TEXT       = "#e2e8f0"
MUTED      = "#8892a4"
ACCENT     = "#6c8ef7"
GREEN      = "#34d399"
YELLOW     = "#fbbf24"
RED        = "#f87171"
FONT_BODY  = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO  = ("Consolas", 11)
FONT_HEAD  = ("Segoe UI", 13, "bold")


def _scrollable(parent) -> ctk.CTkScrollableFrame:
    return ctk.CTkScrollableFrame(parent, fg_color=DARK_BG)


def _card(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=8, **kw)


def _label(parent, text, color=TEXT, font=FONT_BODY, **kw) -> ctk.CTkLabel:
    # Обрезаем слишком длинные строки чтобы не зависал рендер
    if isinstance(text, str) and len(text) > 300:
        text = text[:297] + "…"
    return ctk.CTkLabel(parent, text=text, text_color=color, font=font,
                        anchor="w", justify="left", wraplength=580, **kw)


def _section_title(parent, text: str) -> None:
    ctk.CTkLabel(parent, text=text, text_color=ACCENT, font=FONT_HEAD,
                 anchor="w").pack(fill="x", pady=(16, 4))


def _separator(parent) -> None:
    ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", pady=4)


def _pct_bar(parent, label: str, value: float, color: str = ACCENT) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=3)
    ctk.CTkLabel(row, text=label, text_color=MUTED, font=FONT_SMALL,
                 width=220, anchor="w").pack(side="left")
    bar_bg = ctk.CTkFrame(row, fg_color=BORDER, height=6, corner_radius=3)
    bar_bg.pack(side="left", fill="x", expand=True, padx=(0, 8))
    bar_bg.update_idletasks()
    fill_w = max(0.0, min(1.0, value))
    ctk.CTkFrame(bar_bg, fg_color=color, height=6, corner_radius=3,
                 width=int(200 * fill_w)).place(x=0, y=0)
    ctk.CTkLabel(row, text=f"{int(fill_w*100)}%", text_color=MUTED,
                 font=FONT_SMALL, width=36).pack(side="left")


def _open_url(url: str) -> None:
    webbrowser.open(url)


def _truncate(text: str, max_len: int = 120) -> str:
    if not text:
        return ""
    return text[:max_len] + ("…" if len(text) > max_len else "")


def build_result_tabs(notebook: ctk.CTkTabview, result: AnalysisResult) -> None:
    _build_summary_tab(notebook.tab("Итог"), result)
    # Вкладки Интернет и AI строятся с задержкой чтобы не блокировать UI
    notebook.tab("Интернет").after(50, lambda: _build_internet_tab(notebook.tab("Интернет"), result))
    notebook.tab("AI-анализ").after(100, lambda: _build_ai_tab(notebook.tab("AI-анализ"), result))
    _build_metadata_tab(notebook.tab("Метаданные"), result)
    _build_forensics_tab(notebook.tab("Forensics"), result)
    _build_report_tab(notebook.tab("Отчёт"), result)


def _build_summary_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    rs = result.risk_score
    if not rs:
        _label(scroll, "Оценка рисков не была вычислена.").pack(pady=20)
        return

    trust_cfg = {
        TrustLevel.HIGH:    ("🟢 ВЫСОКИЙ уровень доверия",    GREEN),
        TrustLevel.MEDIUM:  ("🟡 СРЕДНИЙ уровень доверия",    YELLOW),
        TrustLevel.LOW:     ("🔴 НИЗКИЙ уровень доверия",     RED),
        TrustLevel.UNKNOWN: ("⚪ Уровень не определён",        MUTED),
    }
    badge_text, badge_color = trust_cfg.get(rs.overall_trust_level, ("⚪", MUTED))
    badge = _card(scroll)
    badge.pack(fill="x", pady=(8, 0))
    ctk.CTkLabel(badge, text=badge_text, text_color=badge_color,
                 font=("Segoe UI", 15, "bold"), anchor="w").pack(padx=16, pady=12)

    bars_card = _card(scroll)
    bars_card.pack(fill="x", pady=8)
    bars_inner = ctk.CTkFrame(bars_card, fg_color="transparent")
    bars_inner.pack(fill="x", padx=16, pady=12)
    _pct_bar(bars_inner, "Интернет-провенанс",       rs.internet_provenance_score,    ACCENT)
    _pct_bar(bars_inner, "Достоверность метаданных", rs.metadata_confidence_score,    GREEN)
    _pct_bar(bars_inner, "Подозрение на AI",         rs.ai_suspicion_score,           RED)
    _pct_bar(bars_inner, "Подозрение на монтаж",     rs.manipulation_suspicion_score, YELLOW)
    _pct_bar(bars_inner, "Достоверность геолокации", rs.geolocation_confidence_score, "#a78bfa")

    if rs.red_flags:
        _section_title(scroll, "⚠️  Подозрительные признаки")
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        for flag in rs.red_flags:
            _label(inner, f"• {flag}", color=RED, font=FONT_SMALL).pack(fill="x", pady=1)

    if rs.authenticity_arguments:
        _section_title(scroll, "✅  Аргументы в пользу подлинности")
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        for arg in rs.authenticity_arguments:
            _label(inner, f"• {arg}", color=GREEN, font=FONT_SMALL).pack(fill="x", pady=1)

    _section_title(scroll, "Что проверялось")
    card = _card(scroll)
    card.pack(fill="x", pady=4)
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="x", padx=16, pady=10)
    for item in rs.what_was_checked:
        _label(inner, f"✓  {item}", color=GREEN, font=FONT_SMALL).pack(fill="x", pady=1)
    for item in rs.what_was_skipped:
        _label(inner, f"–  {item}", color=MUTED, font=FONT_SMALL).pack(fill="x", pady=1)

    disc = ctk.CTkFrame(scroll, fg_color="#1a1408", corner_radius=8,
                        border_color="#92400e", border_width=1)
    disc.pack(fill="x", pady=12)
    ctk.CTkLabel(
        disc,
        text="⚠️  Это предварительный OSINT/forensic-анализ, не судебная экспертиза.\n"
             "Результаты носят вероятностный характер.",
        text_color=YELLOW, font=FONT_SMALL, wraplength=600, justify="left", anchor="w",
    ).pack(padx=14, pady=10)


def _build_internet_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    rs = result.reverse_search
    if not rs:
        _label(scroll, "Обратный поиск не выполнялся.", color=MUTED).pack(pady=20)
        return

    if rs.earliest_found_url:
        card = _card(scroll)
        card.pack(fill="x", pady=8)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        _label(inner, "📅  Ранний найденный источник:", color=ACCENT).pack(fill="x")
        _label(inner, _truncate(rs.earliest_found_url, 100), color=GREEN, font=FONT_SMALL).pack(fill="x")
        if rs.earliest_found_date:
            _label(inner, rs.earliest_found_date, color=MUTED, font=FONT_SMALL).pack(fill="x")

    _section_title(scroll, "Результаты по сервисам")

    for match in rs.matches:
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")

        if match.error:
            # Обрезаем длинные ошибки — это главная причина зависания
            short_error = _truncate(str(match.error), 80)
            status_text = f"⚠️ Ошибка: {short_error}"
            status_color = RED
        elif match.match_type == "manual_fallback":
            status_text = "🔗 Ручная проверка"
            status_color = YELLOW
        elif match.found:
            status_text = "✓ Найдено"
            status_color = GREEN
        else:
            status_text = "Не найдено"
            status_color = MUTED

        ctk.CTkLabel(header, text=match.service, text_color=ACCENT,
                     font=FONT_HEAD, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text=status_text, text_color=status_color,
                     font=FONT_SMALL, wraplength=300).pack(side="right")

        if match.url and match.url.startswith("http"):
            url_row = ctk.CTkFrame(inner, fg_color="transparent")
            url_row.pack(fill="x", pady=2)
            short = _truncate(match.url, 80)
            ctk.CTkLabel(url_row, text=short, text_color=MUTED,
                         font=FONT_SMALL, anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(url_row, text="Открыть", width=72, height=24,
                          fg_color=BORDER, hover_color=ACCENT, text_color=TEXT,
                          font=FONT_SMALL,
                          command=lambda u=match.url: _open_url(u)).pack(side="right")

        if match.page_title:
            _label(inner, _truncate(match.page_title, 100), color=MUTED, font=FONT_SMALL).pack(fill="x")
        if match.first_seen_date:
            _label(inner, f"Дата: {match.first_seen_date}", color=MUTED, font=FONT_SMALL).pack(fill="x")
        if match.similarity_score is not None:
            _label(inner, f"Сходство: {match.similarity_score:.0%}", color=MUTED, font=FONT_SMALL).pack(fill="x")

    if rs.skipped_services:
        _section_title(scroll, "Пропущено")
        for svc in rs.skipped_services:
            _label(scroll, f"–  {svc}", color=MUTED, font=FONT_SMALL).pack(fill="x", padx=8)


def _build_ai_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    ai = result.ai_detection
    if not ai:
        _label(scroll, "AI-анализ не выполнялся.", color=MUTED).pack(pady=20)
        return

    verdict_colors = {
        AISuspicion.NONE:           GREEN,
        AISuspicion.WEAK:           YELLOW,
        AISuspicion.MODERATE:       YELLOW,
        AISuspicion.STRONG:         RED,
        AISuspicion.CONTRADICTORY:  YELLOW,
        AISuspicion.INSUFFICIENT:   MUTED,
    }
    v_color = verdict_colors.get(ai.overall_suspicion, MUTED)
    card = _card(scroll)
    card.pack(fill="x", pady=8)
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="x", padx=16, pady=12)
    _label(inner, "Итоговый вывод:", color=MUTED, font=FONT_SMALL).pack(fill="x")
    _label(inner, ai.overall_suspicion.value, color=v_color, font=FONT_HEAD).pack(fill="x")

    if ai.ai_suspicion_score > 0:
        _pct_bar(inner, "AI suspicion score", ai.ai_suspicion_score, RED)

    if ai.service_results:
        _section_title(scroll, "Результаты сервисов")
        for svc in ai.service_results:
            card = _card(scroll)
            card.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=10)
            _label(inner, svc.service, color=ACCENT, font=FONT_HEAD).pack(fill="x")
            if svc.error:
                _label(inner, f"Ошибка: {_truncate(str(svc.error), 100)}", color=RED, font=FONT_SMALL).pack(fill="x")
            else:
                _label(inner, _truncate(svc.verdict, 150), color=TEXT, font=FONT_SMALL).pack(fill="x")
                if svc.ai_probability is not None:
                    _pct_bar(inner, "Вероятность AI", svc.ai_probability, RED)

    if ai.local_heuristics_flags:
        _section_title(scroll, "Локальные эвристики")
        note = _card(scroll)
        note.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(note, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        for flag in ai.local_heuristics_flags:
            _label(inner, f"• {_truncate(flag, 150)}", color=MUTED, font=FONT_SMALL).pack(fill="x", pady=1)
        _label(inner,
               "\nЭвристики — мягкие сигналы, не доказательство AI-генерации.",
               color=MUTED, font=FONT_SMALL).pack(fill="x", pady=(6, 0))


def _build_metadata_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    m = result.metadata
    if not m:
        _label(scroll, "Метаданные не были извлечены.", color=MUTED).pack(pady=20)
        return

    for w in m.warnings:
        warn_card = ctk.CTkFrame(scroll, fg_color="#1a1408", corner_radius=8,
                                 border_color="#92400e", border_width=1)
        warn_card.pack(fill="x", pady=4)
        ctk.CTkLabel(warn_card, text=f"⚠️  {w}", text_color=YELLOW,
                     font=FONT_SMALL, wraplength=600, justify="left",
                     anchor="w").pack(padx=12, pady=8)

    fields = [
        ("Производитель камеры", m.camera_make),
        ("Модель камеры",        m.camera_model),
        ("Программа/ПО",         m.software),
        ("Дата съёмки",          m.datetime_original),
        ("Дата изменения",       m.datetime_modified),
        ("Ориентация",           m.orientation),
        ("Объектив",             m.lens_model),
        ("Диафрагма",            m.aperture),
        ("Выдержка",             m.shutter_speed),
        ("ISO",                  m.iso),
        ("Фокусное расстояние",  m.focal_length),
        ("Thumbnail",            "Есть" if m.has_thumbnail else "Нет"),
    ]
    if m.editing_software_detected:
        fields.append(("⚠️ Редактор обнаружен", m.editing_software_detected))

    _section_title(scroll, "EXIF")
    card = _card(scroll)
    card.pack(fill="x", pady=4)
    table = ctk.CTkFrame(card, fg_color="transparent")
    table.pack(fill="x", padx=16, pady=10)
    for label, value in fields:
        if not value:
            continue
        row = ctk.CTkFrame(table, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, text_color=MUTED, font=FONT_SMALL,
                     width=200, anchor="w").pack(side="left")
        color = RED if "⚠️" in label else TEXT
        ctk.CTkLabel(row, text=str(value)[:100], text_color=color,
                     font=FONT_SMALL, anchor="w").pack(side="left", fill="x")

    if m.gps:
        _section_title(scroll, "📍  GPS")
        gps_card = _card(scroll)
        gps_card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(gps_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        _label(inner, f"Широта:   {m.gps.latitude}", font=FONT_SMALL).pack(fill="x")
        _label(inner, f"Долгота:  {m.gps.longitude}", font=FONT_SMALL).pack(fill="x")
        if m.gps.altitude is not None:
            _label(inner, f"Высота:   {m.gps.altitude:.1f} м", font=FONT_SMALL).pack(fill="x")
        if m.gps.reverse_geocode_address:
            _label(inner, f"Адрес:    {m.gps.reverse_geocode_address}", font=FONT_SMALL).pack(fill="x")
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=8)
        ctk.CTkButton(btn_row, text="OpenStreetMap", width=140, height=28,
                      fg_color=BORDER, hover_color=ACCENT, text_color=TEXT,
                      command=lambda: _open_url(m.gps.openstreetmap_url)
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Google Maps", width=120, height=28,
                      fg_color=BORDER, hover_color=ACCENT, text_color=TEXT,
                      command=lambda: _open_url(m.gps.google_maps_url)
                      ).pack(side="left")

    if m.raw_exif:
        _section_title(scroll, "Полный EXIF (raw)")
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        txt = ctk.CTkTextbox(card, height=200, fg_color=BORDER, text_color=MUTED,
                             font=FONT_MONO)
        txt.pack(fill="x", padx=8, pady=8)
        for k, v in sorted(m.raw_exif.items()):
            txt.insert("end", f"{k}: {str(v)[:100]}\n")
        txt.configure(state="disabled")


def _build_forensics_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    f = result.forensics
    h = result.hashes

    if not f:
        _label(scroll, "Forensic-анализ не выполнялся.", color=MUTED).pack(pady=20)
        return

    _section_title(scroll, "Информация о файле")
    card = _card(scroll)
    card.pack(fill="x", pady=4)
    table = ctk.CTkFrame(card, fg_color="transparent")
    table.pack(fill="x", padx=16, pady=10)
    _row(table, "Формат",           f.format)
    _row(table, "Размер",           f"{f.width} × {f.height} пкс")
    _row(table, "Цветовой режим",   f.color_mode)
    _row(table, "Цветовой профиль", f.color_profile or "—")
    _row(table, "Альфа-канал",      "Да" if f.has_alpha else "Нет")
    _row(table, "Размер файла",     f"{f.file_size_bytes / 1024:.1f} КБ")
    if f.jpeg_quality_estimate:
        _row(table, "JPEG качество (оценка)", str(f.jpeg_quality_estimate))

    if f.manipulation_flags:
        _section_title(scroll, "⚠️  Признаки редактирования")
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        for flag in f.manipulation_flags:
            _label(inner, f"• {flag}", color=RED, font=FONT_SMALL).pack(fill="x", pady=1)
    else:
        _label(scroll, "✓  Явных признаков редактирования не обнаружено",
               color=GREEN, font=FONT_SMALL).pack(fill="x", pady=8, padx=8)

    if f.ela:
        _section_title(scroll, "Error Level Analysis (ELA)")
        ela_card = _card(scroll)
        ela_card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(ela_card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        _label(inner, f"Подозрительных пикселей: {f.ela.suspicious_regions_percent:.1f}%",
               font=FONT_SMALL).pack(fill="x")
        _label(inner, f"Макс. разница: {f.ela.max_difference:.1f}  |  Среднее: {f.ela.mean_difference:.2f}",
               color=MUTED, font=FONT_SMALL).pack(fill="x")
        for note in f.ela.notes:
            _label(inner, f"⚠️  {note}", color=YELLOW, font=FONT_SMALL).pack(fill="x", pady=2)
        if f.ela.ela_image_path and Path(f.ela.ela_image_path).exists():
            try:
                from PIL import Image, ImageTk
                ela_pil = Image.open(f.ela.ela_image_path)
                ela_pil.thumbnail((560, 360))
                ela_tk = ImageTk.PhotoImage(ela_pil)
                img_lbl = ctk.CTkLabel(inner, image=ela_tk, text="")
                img_lbl.image = ela_tk
                img_lbl.pack(pady=8)
            except Exception:
                pass

    if h:
        _section_title(scroll, "Хэши")
        card = _card(scroll)
        card.pack(fill="x", pady=4)
        table = ctk.CTkFrame(card, fg_color="transparent")
        table.pack(fill="x", padx=16, pady=10)
        _row(table, "pHash",   h.phash,   mono=True)
        _row(table, "dHash",   h.dhash,   mono=True)
        _row(table, "aHash",   h.ahash,   mono=True)
        _row(table, "wHash",   h.whash,   mono=True)
        _row(table, "MD5",     h.md5,     mono=True)
        _row(table, "SHA-256", h.sha256,  mono=True)
        if h.local_duplicate_found:
            _label(card,
                   f"⚠️  Локальный дубликат: {_truncate(h.local_duplicate_path or '', 60)}  "
                   f"(сходство {h.local_similarity_score:.0%})",
                   color=YELLOW, font=FONT_SMALL).pack(padx=16, pady=4, fill="x")


def _row(parent, label: str, value: str, mono: bool = False) -> None:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=2)
    ctk.CTkLabel(row, text=label, text_color=MUTED, font=FONT_SMALL,
                 width=200, anchor="w").pack(side="left")
    font = FONT_MONO if mono else FONT_SMALL
    ctk.CTkLabel(row, text=str(value), text_color=TEXT,
                 font=font, anchor="w").pack(side="left", fill="x")


def _build_report_tab(frame: ctk.CTkFrame, result: AnalysisResult) -> None:
    _clear(frame)
    scroll = _scrollable(frame)
    scroll.pack(fill="both", expand=True)

    _section_title(scroll, "Экспорт отчёта")
    desc = _card(scroll)
    desc.pack(fill="x", pady=4)
    ctk.CTkLabel(desc, text="Сохраните результаты анализа в удобном формате.",
                 text_color=MUTED, font=FONT_SMALL, anchor="w").pack(padx=16, pady=10)

    btn_card = _card(scroll)
    btn_card.pack(fill="x", pady=4)
    inner = ctk.CTkFrame(btn_card, fg_color="transparent")
    inner.pack(fill="x", padx=16, pady=14)

    base_name = Path(result.image_path).stem

    def save_html():
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML файл", "*.html")],
            initialfile=f"{base_name}_report.html",
        )
        if path:
            generate_html_report(result, path)
            messagebox.showinfo("Сохранено", f"HTML-отчёт сохранён:\n{path}")
            _open_file(path)

    def save_json():
        from tkinter.filedialog import asksaveasfilename
        path = asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON файл", "*.json")],
            initialfile=f"{base_name}_report.json",
        )
        if path:
            generate_json_report(result, path)
            messagebox.showinfo("Сохранено", f"JSON-отчёт сохранён:\n{path}")

    def copy_summary():
        summary = build_short_summary(result)
        frame.clipboard_clear()
        frame.clipboard_append(summary)
        messagebox.showinfo("Скопировано", "Краткий вывод скопирован в буфер обмена.")

    btn_style = dict(height=38, font=("Segoe UI", 12), corner_radius=8)
    ctk.CTkButton(inner, text="💾  Сохранить HTML-отчёт",
                  fg_color=ACCENT, hover_color="#4f72e0", text_color="#fff",
                  command=save_html, **btn_style).pack(fill="x", pady=4)
    ctk.CTkButton(inner, text="📄  Сохранить JSON",
                  fg_color=BORDER, hover_color="#3d4268", text_color=TEXT,
                  command=save_json, **btn_style).pack(fill="x", pady=4)
    ctk.CTkButton(inner, text="📋  Скопировать краткий вывод",
                  fg_color=BORDER, hover_color="#3d4268", text_color=TEXT,
                  command=copy_summary, **btn_style).pack(fill="x", pady=4)

    _section_title(scroll, "Краткий вывод")
    preview_card = _card(scroll)
    preview_card.pack(fill="x", pady=4)
    txt = ctk.CTkTextbox(preview_card, height=220, fg_color=BORDER,
                         text_color=TEXT, font=FONT_MONO)
    txt.pack(fill="x", padx=8, pady=8)
    txt.insert("end", build_short_summary(result))
    txt.configure(state="disabled")


def _clear(frame: ctk.CTkFrame) -> None:
    for widget in frame.winfo_children():
        widget.destroy()


def _open_file(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
    except Exception:
        pass
