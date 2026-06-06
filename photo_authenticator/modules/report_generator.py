"""
modules/report_generator.py — Generates HTML, JSON, and plain-text reports.

HTML report uses an embedded Jinja2 template with inline CSS.
No external dependencies for HTML rendering (no WeasyPrint required for MVP).
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Template

from core.models import AnalysisResult, TrustLevel

logger = logging.getLogger(__name__)


def generate_html_report(result: AnalysisResult, output_path: str) -> str:
    """Render full HTML report and write to output_path. Returns path."""
    html = Template(HTML_TEMPLATE).render(
        result=result,
        TrustLevel=TrustLevel,
        now=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
    )
    Path(output_path).write_text(html, encoding="utf-8")
    logger.info(f"HTML report saved: {output_path}")
    return output_path


def generate_json_report(result: AnalysisResult, output_path: str) -> str:
    """Serialize result to JSON and write to output_path. Returns path."""
    def _default(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        if hasattr(obj, "value"):
            return obj.value
        return str(obj)

    data = json.dumps(result, default=_default, ensure_ascii=False, indent=2)
    Path(output_path).write_text(data, encoding="utf-8")
    logger.info(f"JSON report saved: {output_path}")
    return output_path


def build_short_summary(result: AnalysisResult) -> str:
    """Plain-text short summary for clipboard copy."""
    lines = [
        f"📸 Анализ фотографии: {Path(result.image_path).name}",
        f"🕐 {result.timestamp[:19]}",
        "",
    ]
    if result.risk_score:
        rs = result.risk_score
        trust_emoji = {
            TrustLevel.HIGH: "🟢",
            TrustLevel.MEDIUM: "🟡",
            TrustLevel.LOW: "🔴",
            TrustLevel.UNKNOWN: "⚪",
        }.get(rs.overall_trust_level, "⚪")
        lines.append(f"{trust_emoji} Уровень доверия: {rs.overall_trust_level.value.upper()}")
        lines.append("")
        if rs.red_flags:
            lines.append("⚠️ Подозрительные признаки:")
            for flag in rs.red_flags:
                lines.append(f"  • {flag}")
        if rs.authenticity_arguments:
            lines.append("✅ Аргументы в пользу подлинности:")
            for arg in rs.authenticity_arguments:
                lines.append(f"  • {arg}")
    lines.append("")
    lines.append("⚠️ Это предварительный OSINT/forensic-анализ, не судебная экспертиза.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# HTML Template
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Отчёт об анализе фотографии</title>
<style>
  :root {
    --bg: #0f1117; --card: #1a1d27; --border: #2d3148;
    --text: #e2e8f0; --muted: #8892a4; --accent: #6c8ef7;
    --green: #34d399; --yellow: #fbbf24; --red: #f87171;
    --font: 'Segoe UI', system-ui, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font);
         font-size: 14px; line-height: 1.6; padding: 24px; }
  h1 { font-size: 22px; color: var(--accent); margin-bottom: 4px; }
  h2 { font-size: 16px; color: var(--accent); margin: 20px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  h3 { font-size: 14px; color: var(--text); margin: 14px 0 6px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px;
          padding: 16px; margin-bottom: 16px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px;
           font-size: 12px; font-weight: 600; }
  .badge-high { background: #064e3b; color: var(--green); }
  .badge-medium { background: #451a03; color: var(--yellow); }
  .badge-low { background: #450a0a; color: var(--red); }
  .badge-unknown { background: #1e293b; color: var(--muted); }
  .flag { color: var(--red); }
  .ok { color: var(--green); }
  .muted { color: var(--muted); font-size: 12px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  th { text-align: left; padding: 6px 10px; background: var(--border); color: var(--muted); font-weight: 600; font-size: 12px; }
  td { padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
  .score-bar { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
  .score-bar-label { width: 220px; font-size: 13px; color: var(--muted); }
  .score-bar-track { flex: 1; height: 6px; background: var(--border); border-radius: 3px; }
  .score-bar-fill { height: 100%; border-radius: 3px; }
  .disclaimer { background: #1a1408; border: 1px solid #92400e; border-radius: 6px;
                padding: 12px 16px; color: var(--yellow); margin-top: 20px; font-size: 13px; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  pre { background: var(--border); padding: 10px; border-radius: 6px;
        overflow-x: auto; font-size: 12px; color: #94a3b8; white-space: pre-wrap; }
</style>
</head>
<body>
<h1>📸 Анализ фотографии</h1>
<p class="muted">{{ result.image_path }} &nbsp;·&nbsp; {{ now }}</p>

{% if result.risk_score %}
{% set rs = result.risk_score %}
<div class="card">
  <h2>Итоговая оценка</h2>
  {% set trust = rs.overall_trust_level.value %}
  {% if trust == 'high' %}
    <span class="badge badge-high">🟢 ВЫСОКИЙ уровень доверия</span>
  {% elif trust == 'medium' %}
    <span class="badge badge-medium">🟡 СРЕДНИЙ уровень доверия</span>
  {% elif trust == 'low' %}
    <span class="badge badge-low">🔴 НИЗКИЙ уровень доверия</span>
  {% else %}
    <span class="badge badge-unknown">⚪ Не определён</span>
  {% endif %}

  <div style="margin-top: 16px">
    <div class="score-bar">
      <span class="score-bar-label">Интернет-провенанс</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (rs.internet_provenance_score*100)|round|int }}%;background:#6c8ef7"></div></div>
      <span class="muted">{{ (rs.internet_provenance_score*100)|round|int }}%</span>
    </div>
    <div class="score-bar">
      <span class="score-bar-label">Достоверность метаданных</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (rs.metadata_confidence_score*100)|round|int }}%;background:#34d399"></div></div>
      <span class="muted">{{ (rs.metadata_confidence_score*100)|round|int }}%</span>
    </div>
    <div class="score-bar">
      <span class="score-bar-label">Подозрение на AI-генерацию</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (rs.ai_suspicion_score*100)|round|int }}%;background:#f87171"></div></div>
      <span class="muted">{{ (rs.ai_suspicion_score*100)|round|int }}%</span>
    </div>
    <div class="score-bar">
      <span class="score-bar-label">Подозрение на редактирование</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (rs.manipulation_suspicion_score*100)|round|int }}%;background:#fbbf24"></div></div>
      <span class="muted">{{ (rs.manipulation_suspicion_score*100)|round|int }}%</span>
    </div>
    <div class="score-bar">
      <span class="score-bar-label">Достоверность геолокации</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (rs.geolocation_confidence_score*100)|round|int }}%;background:#a78bfa"></div></div>
      <span class="muted">{{ (rs.geolocation_confidence_score*100)|round|int }}%</span>
    </div>
  </div>

  {% if rs.red_flags %}
  <h3>⚠️ Подозрительные признаки</h3>
  {% for f in rs.red_flags %}<p class="flag">• {{ f }}</p>{% endfor %}
  {% endif %}

  {% if rs.authenticity_arguments %}
  <h3>✅ Аргументы в пользу подлинности</h3>
  {% for a in rs.authenticity_arguments %}<p class="ok">• {{ a }}</p>{% endfor %}
  {% endif %}

  <h3>Что проверялось</h3>
  {% for c in rs.what_was_checked %}<p class="muted">✓ {{ c }}</p>{% endfor %}
  {% if rs.what_was_skipped %}
  <h3>Что пропущено</h3>
  {% for s in rs.what_was_skipped %}<p class="muted">– {{ s }}</p>{% endfor %}
  {% endif %}
</div>
{% endif %}

{% if result.metadata %}
{% set m = result.metadata %}
<h2>Метаданные</h2>
<div class="card">
  <table>
    <tr><th>Поле</th><th>Значение</th></tr>
    {% if m.camera_make %}<tr><td>Производитель</td><td>{{ m.camera_make }}</td></tr>{% endif %}
    {% if m.camera_model %}<tr><td>Модель</td><td>{{ m.camera_model }}</td></tr>{% endif %}
    {% if m.software %}<tr><td>Программа</td><td>{{ m.software }}</td></tr>{% endif %}
    {% if m.datetime_original %}<tr><td>Дата съёмки</td><td>{{ m.datetime_original }}</td></tr>{% endif %}
    {% if m.datetime_modified %}<tr><td>Дата изменения</td><td>{{ m.datetime_modified }}</td></tr>{% endif %}
    {% if m.iso %}<tr><td>ISO</td><td>{{ m.iso }}</td></tr>{% endif %}
    {% if m.aperture %}<tr><td>Диафрагма</td><td>{{ m.aperture }}</td></tr>{% endif %}
    {% if m.shutter_speed %}<tr><td>Выдержка</td><td>{{ m.shutter_speed }}</td></tr>{% endif %}
    {% if m.focal_length %}<tr><td>Фокусное расстояние</td><td>{{ m.focal_length }}</td></tr>{% endif %}
    {% if m.lens_model %}<tr><td>Объектив</td><td>{{ m.lens_model }}</td></tr>{% endif %}
    {% if m.orientation %}<tr><td>Ориентация</td><td>{{ m.orientation }}</td></tr>{% endif %}
  </table>

  {% if m.gps %}
  <h3>📍 GPS-данные</h3>
  <p>Координаты: {{ m.gps.latitude }}, {{ m.gps.longitude }}</p>
  <p><a href="{{ m.gps.openstreetmap_url }}" target="_blank">OpenStreetMap</a>
     &nbsp;·&nbsp;
     <a href="{{ m.gps.google_maps_url }}" target="_blank">Google Maps</a></p>
  {% if m.gps.reverse_geocode_address %}
  <p>Адрес: {{ m.gps.reverse_geocode_address }}</p>
  {% endif %}
  {% endif %}

  {% for w in m.warnings %}
  <p class="flag" style="margin-top:8px">⚠️ {{ w }}</p>
  {% endfor %}
</div>
{% endif %}

{% if result.forensics %}
{% set f = result.forensics %}
<h2>Forensics</h2>
<div class="card">
  <table>
    <tr><td>Формат</td><td>{{ f.format }}</td></tr>
    <tr><td>Размер</td><td>{{ f.width }} × {{ f.height }} пкс</td></tr>
    <tr><td>Цветовой режим</td><td>{{ f.color_mode }}</td></tr>
    <tr><td>Цветовой профиль</td><td>{{ f.color_profile }}</td></tr>
    <tr><td>Альфа-канал</td><td>{{ 'Да' if f.has_alpha else 'Нет' }}</td></tr>
    {% if f.jpeg_quality_estimate %}<tr><td>JPEG качество (оценка)</td><td>{{ f.jpeg_quality_estimate }}</td></tr>{% endif %}
    <tr><td>Размер файла</td><td>{{ (f.file_size_bytes / 1024)|round|int }} КБ</td></tr>
  </table>

  {% if f.ela %}
  <h3>Error Level Analysis</h3>
  {% if f.ela.ela_image_path %}
  <img src="{{ f.ela.ela_image_path }}" alt="ELA" style="max-width:100%;border-radius:4px;margin-top:8px">
  {% endif %}
  <p class="muted">Подозрительных пикселей: {{ f.ela.suspicious_regions_percent|round(1) }}%</p>
  {% for note in f.ela.notes %}<p class="flag">• {{ note }}</p>{% endfor %}
  {% endif %}

  {% for flag in f.manipulation_flags %}
  <p class="flag">⚠️ {{ flag }}</p>
  {% endfor %}
</div>
{% endif %}

{% if result.hashes %}
{% set h = result.hashes %}
<h2>Хэши</h2>
<div class="card">
  <table>
    <tr><th>Алгоритм</th><th>Значение</th></tr>
    <tr><td>pHash</td><td><code>{{ h.phash }}</code></td></tr>
    <tr><td>dHash</td><td><code>{{ h.dhash }}</code></td></tr>
    <tr><td>aHash</td><td><code>{{ h.ahash }}</code></td></tr>
    <tr><td>wHash</td><td><code>{{ h.whash }}</code></td></tr>
    <tr><td>MD5</td><td><code>{{ h.md5 }}</code></td></tr>
    <tr><td>SHA-256</td><td><code>{{ h.sha256 }}</code></td></tr>
  </table>
  {% if h.local_duplicate_found %}
  <p class="flag" style="margin-top:8px">⚠️ Локальный дубликат: {{ h.local_duplicate_path }} (сходство {{ (h.local_similarity_score*100)|round|int }}%)</p>
  {% endif %}
</div>
{% endif %}

{% if result.reverse_search %}
{% set rs2 = result.reverse_search %}
<h2>Обратный поиск</h2>
<div class="card">
  <table>
    <tr><th>Сервис</th><th>Результат</th><th>URL</th><th>Дата</th><th>Тип</th></tr>
    {% for m in rs2.matches %}
    <tr>
      <td>{{ m.service }}</td>
      <td>{% if m.error %}<span class="flag">Ошибка</span>{% elif m.match_type == 'manual_fallback' %}<span class="muted">Ручная проверка</span>{% elif m.found %}<span class="ok">✓ Найдено</span>{% else %}<span class="muted">Не найдено</span>{% endif %}</td>
      <td>{% if m.url %}<a href="{{ m.url }}" target="_blank">{{ m.url[:60] }}{% if m.url|length > 60 %}…{% endif %}</a>{% endif %}</td>
      <td>{{ m.first_seen_date or '—' }}</td>
      <td>{{ m.match_type or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}

{% if result.ai_detection %}
{% set ai = result.ai_detection %}
<h2>AI-анализ</h2>
<div class="card">
  <p><strong>Итог:</strong> {{ ai.overall_suspicion.value }}</p>
  {% for svc in ai.service_results %}
  <h3>{{ svc.service }}</h3>
  {% if svc.error %}<p class="flag">Ошибка: {{ svc.error }}</p>
  {% else %}
    <p>{{ svc.verdict }}</p>
    {% if svc.ai_probability is not none %}
    <p class="muted">Вероятность AI: {{ (svc.ai_probability*100)|round(1) }}%</p>
    {% endif %}
  {% endif %}
  {% endfor %}

  {% if ai.local_heuristics_flags %}
  <h3>Локальные эвристики</h3>
  {% for f in ai.local_heuristics_flags %}<p class="muted">• {{ f }}</p>{% endfor %}
  {% endif %}
</div>
{% endif %}

{% if result.errors %}
<h2>Ошибки</h2>
<div class="card">
{% for e in result.errors %}<p class="flag">• {{ e }}</p>{% endfor %}
</div>
{% endif %}

<div class="disclaimer">
  ⚠️ Этот отчёт является предварительным OSINT/forensic-анализом и не является судебной экспертизой.
  Программа не утверждает, что фото «точно настоящее» или «точно фейк».
  Все выводы носят вероятностный характер и требуют дополнительной проверки при необходимости.
</div>

</body>
</html>"""
