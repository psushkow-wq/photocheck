"""
ui/main_window.py — Main application window.

Layout:
  Left panel  — image drop/load zone + controls + progress log
  Right panel — tabbed result view

The analysis pipeline runs in a background thread; progress is
forwarded to the UI via thread-safe after() callbacks.
"""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from config import Config
from core.models import AnalysisResult
from core.pipeline import run_pipeline
from ui.result_tabs import build_result_tabs

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DARK_BG   = "#0f1117"
CARD_BG   = "#1a1d27"
BORDER    = "#2d3148"
TEXT      = "#e2e8f0"
MUTED     = "#8892a4"
ACCENT    = "#6c8ef7"
GREEN     = "#34d399"
YELLOW    = "#fbbf24"
RED       = "#f87171"

FONT_BODY = ("Segoe UI", 12)
FONT_HEAD = ("Segoe UI", 13, "bold")
FONT_TINY = ("Segoe UI", 10)

THUMB_SIZE = (320, 320)


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Photo Authenticator")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.configure(fg_color=DARK_BG)

        self._image_path: Optional[str] = None
        self._analysis_result: Optional[AnalysisResult] = None
        self._running = False
        self._thumb_ref = None  # keep PhotoImage reference alive

        self._build_ui()
        self._setup_dnd()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Main two-column layout
        self.grid_columnconfigure(0, weight=0, minsize=360)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._left  = self._build_left_panel()
        self._right = self._build_right_panel()

    def _build_left_panel(self) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, width=360)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_rowconfigure(3, weight=1)

        # ── Title ──────────────────────────────────────────────────────────
        title_row = ctk.CTkFrame(panel, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(18, 0))
        ctk.CTkLabel(title_row, text="📸  Photo Authenticator",
                     text_color=ACCENT, font=("Segoe UI", 15, "bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(title_row,
                     text="OSINT/Forensic анализ подлинности фото",
                     text_color=MUTED, font=FONT_TINY, anchor="w").pack(fill="x")

        ctk.CTkFrame(panel, height=1, fg_color=BORDER).grid(
            row=1, column=0, sticky="ew", padx=16, pady=12)

        # ── Drop zone + preview ────────────────────────────────────────────
        drop_frame = ctk.CTkFrame(panel, fg_color=DARK_BG, corner_radius=10,
                                   border_color=BORDER, border_width=1)
        drop_frame.grid(row=2, column=0, sticky="ew", padx=16)

        self._preview_label = ctk.CTkLabel(
            drop_frame,
            text="Перетащите сюда фото\nили нажмите «Загрузить»\n\nJPG · PNG · WEBP · HEIC",
            text_color=MUTED, font=FONT_BODY,
            width=328, height=280,
        )
        self._preview_label.pack(padx=0, pady=0)
        self._preview_label.bind("<Button-1>", lambda _: self._browse_file())

        self._path_label = ctk.CTkLabel(drop_frame, text="", text_color=MUTED,
                                         font=FONT_TINY, wraplength=300)
        self._path_label.pack(pady=(0, 8))

        # ── Controls ───────────────────────────────────────────────────────
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="nsew", padx=16, pady=8)

        ctk.CTkButton(controls, text="📂  Загрузить фото",
                      fg_color=BORDER, hover_color=ACCENT, text_color=TEXT,
                      font=FONT_BODY, height=36,
                      command=self._browse_file).pack(fill="x", pady=3)

        # Mode selector
        ctk.CTkLabel(controls, text="Режим проверки:", text_color=MUTED,
                     font=FONT_TINY, anchor="w").pack(fill="x", pady=(8, 2))
        self._mode_var = tk.StringVar(value=Config.DEFAULT_MODE)
        mode_row = ctk.CTkFrame(controls, fg_color="transparent")
        mode_row.pack(fill="x")
        for label, value in [("Быстрая", "fast"), ("Полная", "full"), ("Только локально", "local")]:
            ctk.CTkRadioButton(mode_row, text=label, variable=self._mode_var, value=value,
                               text_color=TEXT, font=FONT_TINY,
                               radiobutton_width=14, radiobutton_height=14,
                               fg_color=ACCENT).pack(side="left", padx=(0, 10))

        # Consent checkbox
        self._allow_external_var = tk.BooleanVar(value=Config.ALLOW_EXTERNAL_DEFAULT)
        ctk.CTkCheckBox(
            controls,
            text="Разрешаю отправку фото во внешние сервисы",
            variable=self._allow_external_var,
            text_color=TEXT, font=FONT_TINY,
            fg_color=ACCENT, hover_color="#4f72e0",
            checkmark_color="#fff",
        ).pack(fill="x", pady=(8, 2))

        # Available APIs indicator
        apis = Config.available_apis()
        apis_text = f"Доступно API: {', '.join(apis) or 'нет (только локальный анализ)'}"
        ctk.CTkLabel(controls, text=apis_text, text_color=MUTED,
                     font=FONT_TINY, wraplength=310, anchor="w").pack(fill="x", pady=2)

        # Run button
        self._run_btn = ctk.CTkButton(
            controls, text="🔍  Начать проверку",
            fg_color=ACCENT, hover_color="#4f72e0", text_color="#fff",
            font=("Segoe UI", 13, "bold"), height=42,
            command=self._on_run, state="disabled",
        )
        self._run_btn.pack(fill="x", pady=(10, 4))

        # Progress bar
        self._progress = ctk.CTkProgressBar(controls, height=6,
                                             fg_color=BORDER, progress_color=ACCENT)
        self._progress.set(0)
        self._progress.pack(fill="x", pady=4)

        # Log textbox
        ctk.CTkLabel(controls, text="Лог:", text_color=MUTED,
                     font=FONT_TINY, anchor="w").pack(fill="x", pady=(6, 0))
        self._log_box = ctk.CTkTextbox(
            controls, height=140, fg_color=DARK_BG, text_color=MUTED,
            font=("Consolas", 10), wrap="word",
        )
        self._log_box.pack(fill="x")
        self._log_box.configure(state="disabled")

        return panel

    def _build_right_panel(self) -> ctk.CTkFrame:
        panel = ctk.CTkFrame(self, fg_color=DARK_BG, corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self._placeholder = ctk.CTkLabel(
            panel,
            text="Загрузите фото и нажмите «Начать проверку»",
            text_color=MUTED, font=("Segoe UI", 14),
        )
        self._placeholder.grid(row=0, column=0)

        self._notebook: Optional[ctk.CTkTabview] = None
        return panel

    # ─────────────────────────────────────────────────────────────────────────
    # Drag-and-drop
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_dnd(self) -> None:
        """Set up drag-and-drop using tkinterdnd2 if available."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass  # tkinterdnd2 not installed — button-only mode

    def _on_drop(self, event) -> None:
        path = event.data.strip("{}")
        if Path(path).suffix.lower() in Config.SUPPORTED_FORMATS:
            self._load_image(path)

    # ─────────────────────────────────────────────────────────────────────────
    # Image loading
    # ─────────────────────────────────────────────────────────────────────────

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите фотографию",
            filetypes=[
                ("Изображения", "*.jpg *.jpeg *.png *.webp *.heic *.tiff *.bmp"),
                ("Все файлы", "*.*"),
            ],
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str) -> None:
        self._image_path = path
        self._path_label.configure(text=Path(path).name)

        try:
            img = Image.open(path)
            img.thumbnail(THUMB_SIZE)
            self._thumb_ref = ImageTk.PhotoImage(img)
            self._preview_label.configure(image=self._thumb_ref, text="")
        except Exception as e:
            self._preview_label.configure(
                image=None, text=f"Не удалось показать превью:\n{e}"
            )

        self._run_btn.configure(state="normal")
        self._log("Фото загружено: " + Path(path).name)

    # ─────────────────────────────────────────────────────────────────────────
    # Run pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        if self._running or not self._image_path:
            return

        allow = self._allow_external_var.get()
        mode = self._mode_var.get()

        # Consent dialog when external APIs will be used
        if allow and mode != "local":
            apis = Config.available_apis()
            if apis:
                msg = (
                    "Следующие сервисы получат копию вашего изображения:\n\n"
                    + "\n".join(f"  • {a}" for a in apis)
                    + "\n\nПродолжить?"
                )
                if not messagebox.askyesno("Согласие на передачу данных", msg):
                    return

        self._running = True
        self._run_btn.configure(state="disabled", text="⏳  Анализ...")
        self._progress.set(0)
        self._clear_log()

        thread = threading.Thread(
            target=self._run_analysis,
            args=(self._image_path, mode, allow),
            daemon=True,
        )
        thread.start()

    def _run_analysis(self, image_path: str, mode: str, allow_external: bool) -> None:
        def progress_cb(msg: str, frac: float) -> None:
            self.after(0, self._on_progress, msg, frac)

        result = run_pipeline(
            image_path=image_path,
            mode=mode,
            allow_external=allow_external,
            progress_callback=progress_cb,
        )
        self.after(0, self._on_analysis_complete, result)

    def _on_progress(self, msg: str, frac: float) -> None:
        self._log(msg)
        self._progress.set(frac)

    def _on_analysis_complete(self, result: AnalysisResult) -> None:
        self._running = False
        self._analysis_result = result
        self._run_btn.configure(state="normal", text="🔍  Начать проверку")
        self._progress.set(1.0)

        if result.errors:
            for err in result.errors:
                self._log(f"⚠️  {err}")

        self._show_results(result)

    # ─────────────────────────────────────────────────────────────────────────
    # Results display
    # ─────────────────────────────────────────────────────────────────────────

    def _show_results(self, result: AnalysisResult) -> None:
        # Remove placeholder
        self._placeholder.grid_forget()

        # Recreate notebook each time (clean state)
        if self._notebook:
            self._notebook.grid_forget()
            self._notebook.destroy()

        self._notebook = ctk.CTkTabview(
            self._right,
            fg_color=DARK_BG,
            segmented_button_fg_color=CARD_BG,
            segmented_button_selected_color=ACCENT,
            segmented_button_unselected_color=CARD_BG,
            segmented_button_selected_hover_color="#4f72e0",
            text_color=TEXT,
        )
        self._notebook.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        for tab_name in ["Итог", "Интернет", "AI-анализ", "Метаданные", "Forensics", "Отчёт"]:
            self._notebook.add(tab_name)

        build_result_tabs(self._notebook, result)
        self._notebook.set("Итог")

    # ─────────────────────────────────────────────────────────────────────────
    # Log helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
