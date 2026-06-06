"""
PhotoCheck — Multi-language photo verification service.
No registration required. Open access.
Languages: RU, EN, ET
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, session, g

ENGINE_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(ENGINE_PATH))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "photocheck-secret-2025")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

UPLOAD_TMP = Path(tempfile.gettempdir()) / "photocheck_uploads"
UPLOAD_TMP.mkdir(exist_ok=True)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".bmp"}
SUPPORTED_LANGS = ["ru", "en", "et"]
DEFAULT_LANG = "en"

# ── Translations ──────────────────────────────────────────────────────────────

T = {
    "ru": {
        "site_name": "PhotoCheck",
        "tagline": "Проверьте фото за секунды",
        "description": "Одно место — все проверки. Загрузите фото и мы автоматически проверим его через Google Lens, AI-детекторы и forensic-анализ. Без регистрации на десятках сайтов.",
        "cta_primary": "Проверить фото →",
        "nav_tool": "Инструмент",
        "stat_analyses": "Фото проверено",
        "stat_visits": "Посещений",
        "stat_methods": "Методов анализа",
        "features_title": "Все проверки — в одном месте",
        "features_sub": "Раньше нужно было открывать Google Lens, проверять EXIF в отдельных сервисах... Теперь всё это делается одной кнопкой.",
        "f1_title": "Метаданные EXIF", "f1_desc": "Камера, дата съёмки, GPS-координаты — всё что скрыто в файле.",
        "f2_title": "GPS и геолокация", "f2_desc": "Где сделан снимок — с точностью до адреса, с ссылками на карты.",
        "f3_title": "ELA Forensics", "f3_desc": "Выявляем следы монтажа и повторного сжатия — то, что не видно глазу.",
        "f4_title": "AI детекция", "f4_desc": "Midjourney, DALL-E, Stable Diffusion — определяем вероятность генерации.",
        "f5_title": "Обратный поиск", "f5_desc": "Google Lens — находим все источники фото в интернете.",
        "f6_title": "Хэши и дубликаты", "f6_desc": "Уникальный цифровой отпечаток фото для поиска копий.",
        "how_title": "Три шага", "how_sub": "Никаких сложных настроек. Просто загрузите фото.",
        "step1_title": "Откройте инструмент", "step1_desc": "Регистрация не нужна. Просто нажмите «Проверить фото».",
        "step2_title": "Загрузите фото", "step2_desc": "JPG, PNG, WEBP, HEIC — любой формат с телефона или компьютера.",
        "step3_title": "Получите анализ", "step3_desc": "Через 15–30 секунд — полный отчёт по всем параметрам.",
        "cta_title": "Готовы проверить?", "cta_sub": "Бесплатно. Без регистрации. Без лишних сайтов.",
        "footer_desc": "Проверка фотографий через множество сервисов — в одном месте.",
        "tool_title": "Проверка фото", "tool_sub": "Загрузите фотографию для анализа",
        "upload_title": "Загрузить фотографию",
        "upload_sub": "Нажмите или перетащите · JPG PNG WEBP HEIC до 50 МБ",
        "chip_ext": "🌐 Внешние API", "chip_full": "🔬 Полный режим",
        "btn_analyze": "🔍 Анализировать",
        "tab_summary": "Итог", "tab_meta": "Данные", "tab_forensics": "Forensics",
        "tab_internet": "Интернет", "tab_ai": "AI",
        "trust_high": "🟢 Высокий уровень доверия", "trust_medium": "🟡 Средний уровень доверия",
        "trust_low": "🔴 Низкий уровень доверия", "trust_unknown": "⚪ Не определён",
        "disclaimer": "Это предварительный OSINT/forensic-анализ, не судебная экспертиза.",
        "err_no_file": "Файл не загружен", "err_format": "Неподдерживаемый формат",
        "ad_label": "Реклама",
        "cookie_text": "Мы используем cookies для хранения языковых настроек. Продолжая использовать сайт, вы соглашаетесь с этим.",
        "cookie_ok": "Понятно",
        "upload_warning_title": "⚠️ Важно перед загрузкой",
        "upload_warning_text": "Для обратного поиска через Google Lens ваше фото временно загружается на сторонний сервис (freeimage.host) и автоматически удаляется через 10 минут. Не загружайте личные или конфиденциальные фотографии.",
        "upload_warning_accept": "Понятно, продолжить",
        "upload_warning_decline": "Отключить внешний поиск",
        "privacy_title": "Конфиденциальность",
        "privacy_text": "PhotoCheck не требует регистрации и не хранит ваши фотографии. Для поиска в Google Lens фото временно загружается на freeimage.host и удаляется через 10 минут. Мы используем cookies только для языковых настроек.",
    },
    "en": {
        "site_name": "PhotoCheck",
        "tagline": "Verify any photo in seconds",
        "description": "One place — all checks. Upload a photo and we automatically verify it through Google Lens, AI detectors and forensic analysis. No need to register on dozens of sites.",
        "cta_primary": "Check photo →",
        "nav_tool": "Tool",
        "stat_analyses": "Photos checked",
        "stat_visits": "Visits",
        "stat_methods": "Analysis methods",
        "features_title": "All checks — one place",
        "features_sub": "You used to open Google Lens, check EXIF in separate services... Now everything is done with one click.",
        "f1_title": "EXIF Metadata", "f1_desc": "Camera model, shooting date, GPS coordinates — everything hidden in the file.",
        "f2_title": "GPS & Geolocation", "f2_desc": "Where was the shot taken — down to the address, with map links.",
        "f3_title": "ELA Forensics", "f3_desc": "We detect traces of editing and re-compression — invisible to the naked eye.",
        "f4_title": "AI Detection", "f4_desc": "Midjourney, DALL-E, Stable Diffusion — we determine the probability of AI generation.",
        "f5_title": "Reverse Search", "f5_desc": "Google Lens — find all sources of the photo on the internet.",
        "f6_title": "Hashes & Duplicates", "f6_desc": "A unique digital fingerprint of the photo to search for copies.",
        "how_title": "Three steps", "how_sub": "No complex setup. Just upload your photo.",
        "step1_title": "Open the tool", "step1_desc": "No registration needed. Just click 'Check photo'.",
        "step2_title": "Upload a photo", "step2_desc": "JPG, PNG, WEBP, HEIC — any format from phone or computer.",
        "step3_title": "Get the analysis", "step3_desc": "In 15–30 seconds — a full report on all parameters.",
        "cta_title": "Ready to check?", "cta_sub": "Free. No registration. No extra sites.",
        "footer_desc": "Photo verification through multiple services — in one place.",
        "tool_title": "Photo Check", "tool_sub": "Upload a photo for analysis",
        "upload_title": "Upload photo",
        "upload_sub": "Click or drag · JPG PNG WEBP HEIC up to 50 MB",
        "chip_ext": "🌐 External APIs", "chip_full": "🔬 Full mode",
        "btn_analyze": "🔍 Analyze",
        "tab_summary": "Summary", "tab_meta": "Metadata", "tab_forensics": "Forensics",
        "tab_internet": "Internet", "tab_ai": "AI",
        "trust_high": "🟢 High trust level", "trust_medium": "🟡 Medium trust level",
        "trust_low": "🔴 Low trust level", "trust_unknown": "⚪ Unknown",
        "disclaimer": "This is a preliminary OSINT/forensic analysis, not a legal expert opinion.",
        "err_no_file": "No file uploaded", "err_format": "Unsupported format",
        "ad_label": "Advertisement",
        "cookie_text": "We use cookies to store language preferences. By continuing to use the site, you agree to this.",
        "cookie_ok": "Got it",
        "upload_warning_title": "⚠️ Important before uploading",
        "upload_warning_text": "For reverse search via Google Lens, your photo is temporarily uploaded to a third-party service (freeimage.host) and automatically deleted after 10 minutes. Do not upload personal or confidential photos.",
        "upload_warning_accept": "Understood, continue",
        "upload_warning_decline": "Disable external search",
        "privacy_title": "Privacy",
        "privacy_text": "PhotoCheck does not require registration and does not store your photos. For Google Lens search, the photo is temporarily uploaded to freeimage.host and deleted after 10 minutes. We use cookies only for language settings.",
    },
    "et": {
        "site_name": "PhotoCheck",
        "tagline": "Kontrolli fotot sekunditega",
        "description": "Üks koht — kõik kontrollid. Laadi foto üles ja me kontrollime seda automaatselt Google Lens'i, AI-detektorite ja kohtuekspertiisi abil. Ei pea registreeruma kümnetel saitidel.",
        "cta_primary": "Kontrolli fotot →",
        "nav_tool": "Tööriist",
        "stat_analyses": "Fotot kontrollitud",
        "stat_visits": "Külastust",
        "stat_methods": "Analüüsimeetodit",
        "features_title": "Kõik kontrollid — ühes kohas",
        "features_sub": "Varem pidid avama Google Lens'i... Nüüd teeb kõik üks nupp.",
        "f1_title": "EXIF metaandmed", "f1_desc": "Kaamera mudel, pildistamise kuupäev, GPS-koordinaadid — kõik, mis on failis peidetud.",
        "f2_title": "GPS ja geolokatsioon", "f2_desc": "Kus pilt tehti — täpsusega aadressini, kaardilinkidega.",
        "f3_title": "ELA kohtuekspertiis", "f3_desc": "Tuvastame montaaži ja taasvormindamise jäljed — palja silmaga nähtamatud.",
        "f4_title": "AI tuvastamine", "f4_desc": "Midjourney, DALL-E, Stable Diffusion — määrame AI genereerimise tõenäosuse.",
        "f5_title": "Pöördotsing", "f5_desc": "Google Lens — leiame kõik foto allikad internetist.",
        "f6_title": "Räsid ja duplikaadid", "f6_desc": "Foto unikaalne digitaalne sõrmejälg koopiate otsimiseks.",
        "how_title": "Kolm sammu", "how_sub": "Keerulisi seadistusi pole. Lihtsalt laadi foto üles.",
        "step1_title": "Ava tööriist", "step1_desc": "Registreerimine pole vajalik. Kliki lihtsalt 'Kontrolli fotot'.",
        "step2_title": "Laadi foto üles", "step2_desc": "JPG, PNG, WEBP, HEIC — ükskõik milline formaat telefonist või arvutist.",
        "step3_title": "Saa analüüs", "step3_desc": "15–30 sekundi jooksul — täielik aruanne kõigi parameetrite kohta.",
        "cta_title": "Valmis kontrollima?", "cta_sub": "Tasuta. Ilma registreerimiseta. Ilma lisasaitideta.",
        "footer_desc": "Fotode kontrollimine mitme teenuse kaudu — ühes kohas.",
        "tool_title": "Foto kontroll", "tool_sub": "Laadi foto analüüsimiseks üles",
        "upload_title": "Laadi foto üles",
        "upload_sub": "Kliki või lohista · JPG PNG WEBP HEIC kuni 50 MB",
        "chip_ext": "🌐 Välised API-d", "chip_full": "🔬 Täisrežiim",
        "btn_analyze": "🔍 Analüüsi",
        "tab_summary": "Kokkuvõte", "tab_meta": "Andmed", "tab_forensics": "Ekspertiis",
        "tab_internet": "Internet", "tab_ai": "AI",
        "trust_high": "🟢 Kõrge usaldustase", "trust_medium": "🟡 Keskmine usaldustase",
        "trust_low": "🔴 Madal usaldustase", "trust_unknown": "⚪ Määramata",
        "disclaimer": "See on esialgne OSINT/kohtuekspertiisi analüüs, mitte kohtuekspertiisi arvamus.",
        "err_no_file": "Faili ei laaditud üles", "err_format": "Toetamata formaat",
        "ad_label": "Reklaam",
        "cookie_text": "Kasutame küpsiseid keeleseadete salvestamiseks. Saidi kasutamist jätkates nõustute sellega.",
        "cookie_ok": "Selge",
        "upload_warning_title": "⚠️ Oluline enne üleslaadimist",
        "upload_warning_text": "Google Lens'i pöördotsinguks laaditakse teie foto ajutiselt kolmanda osapoole teenusesse (freeimage.host) ja kustutatakse automaatselt 10 minuti pärast. Ärge laadige üles isiklikke ega konfidentsiaalseid fotosid.",
        "upload_warning_accept": "Selge, jätkan",
        "upload_warning_decline": "Keela väline otsing",
        "privacy_title": "Privaatsus",
        "privacy_text": "PhotoCheck ei nõua registreerimist ega salvesta teie fotosid. Google Lens'i otsingul laaditakse foto ajutiselt freeimage.host'i ja kustutatakse 10 minuti pärast. Kasutame küpsiseid ainult keeleseadete jaoks.",
    },
}

# ── Simple stats (no DB, just file) ───────────────────────────────────────────
import json, threading
STATS_FILE = Path(__file__).parent / "data" / "stats.json"
STATS_FILE.parent.mkdir(exist_ok=True)
_stats_lock = threading.Lock()

def get_stats():
    try:
        return json.loads(STATS_FILE.read_text())
    except:
        return {"total_visits": 0, "total_analyses": 0}

def inc_stat(key):
    with _stats_lock:
        s = get_stats()
        s[key] = s.get(key, 0) + 1
        STATS_FILE.write_text(json.dumps(s))

# ── Language ──────────────────────────────────────────────────────────────────

@app.before_request
def set_lang():
    lang = request.args.get("lang") or session.get("lang")
    if not lang:
        accept = request.headers.get("Accept-Language", "")
        for l in SUPPORTED_LANGS:
            if l in accept:
                lang = l
                break
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    session["lang"] = lang
    g.lang = lang
    g.t = T[lang]
    if not request.path.startswith("/static"):
        inc_stat("total_visits")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = get_stats()
    return render_template("index.html", stats=stats, t=g.t, lang=g.lang)

@app.route("/set-lang/<lang>")
def set_language(lang):
    if lang in SUPPORTED_LANGS:
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))

@app.route("/tool")
def tool():
    return render_template("tool.html", t=g.t, lang=g.lang)

@app.route("/privacy")
def privacy():
    return render_template("privacy.html", t=g.t, lang=g.lang)

@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": g.t["err_no_file"]}), 400
    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return jsonify({"error": g.t["err_format"]}), 400

    tmp = UPLOAD_TMP / f"{uuid.uuid4()}{suffix}"
    file.save(str(tmp))
    try:
        from config import Config, setup_logging
        from core.pipeline import run_pipeline
        setup_logging()
        result = run_pipeline(str(tmp),
                              mode=request.form.get("mode", "fast"),
                              allow_external=request.form.get("allow_external", "true") == "true")
        inc_stat("total_analyses")
        return jsonify(_serialize(result, g.lang))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp.exists():
            tmp.unlink()

@app.route("/ela_image")
def ela_image():
    path = request.args.get("path", "")
    if path and Path(path).exists():
        return send_file(path, mimetype="image/jpeg")
    return "", 404

# ── Serialization ─────────────────────────────────────────────────────────────

def _serialize(result, lang="en") -> dict:
    from core.models import TrustLevel
    t = T[lang]
    out = {"risk": None, "metadata": None, "hashes": None,
           "forensics": None, "reverse_search": None, "ai_detection": None}

    if result.risk_score:
        rs = result.risk_score
        lvl_map = {
            TrustLevel.HIGH:    ("high",    t["trust_high"]),
            TrustLevel.MEDIUM:  ("medium",  t["trust_medium"]),
            TrustLevel.LOW:     ("low",     t["trust_low"]),
            TrustLevel.UNKNOWN: ("unknown", t["trust_unknown"]),
        }
        level, label = lvl_map.get(rs.overall_trust_level, ("unknown", t["trust_unknown"]))
        out["risk"] = {
            "level": level, "label": label,
            "internet_provenance": round(rs.internet_provenance_score * 100),
            "metadata_confidence": round(rs.metadata_confidence_score * 100),
            "ai_suspicion": round(rs.ai_suspicion_score * 100),
            "manipulation_suspicion": round(rs.manipulation_suspicion_score * 100),
            "geolocation_confidence": round(rs.geolocation_confidence_score * 100),
            "red_flags": rs.red_flags,
            "authenticity_arguments": rs.authenticity_arguments,
        }

    if result.metadata:
        m = result.metadata
        out["metadata"] = {
            "camera_make": m.camera_make, "camera_model": m.camera_model,
            "software": m.software, "datetime_original": m.datetime_original,
            "datetime_modified": m.datetime_modified, "iso": m.iso,
            "aperture": m.aperture, "shutter_speed": m.shutter_speed,
            "focal_length": m.focal_length, "editing_software": m.editing_software_detected,
            "warnings": m.warnings,
            "gps": {
                "latitude": m.gps.latitude, "longitude": m.gps.longitude,
                "address": m.gps.reverse_geocode_address,
                "osm_url": m.gps.openstreetmap_url, "gmaps_url": m.gps.google_maps_url,
            } if m.gps else None,
        }

    if result.hashes:
        h = result.hashes
        out["hashes"] = {
            "phash": h.phash, "md5": h.md5, "sha256": h.sha256,
            "duplicate_found": h.local_duplicate_found,
            "duplicate_similarity": round(h.local_similarity_score * 100) if h.local_similarity_score else 0,
        }

    if result.forensics:
        f = result.forensics
        ela_path = None
        if f.ela and f.ela.ela_image_path and Path(f.ela.ela_image_path).exists():
            ela_path = f.ela.ela_image_path
        out["forensics"] = {
            "format": f.format, "width": f.width, "height": f.height,
            "file_size_kb": round(f.file_size_bytes / 1024, 1),
            "jpeg_quality": f.jpeg_quality_estimate,
            "manipulation_flags": f.manipulation_flags,
            "ela": {
                "suspicious_percent": round(f.ela.suspicious_regions_percent, 1),
                "notes": f.ela.notes, "image_path": ela_path,
            } if f.ela else None,
        }

    if result.reverse_search:
        out["reverse_search"] = {"matches": [
            {
                "service": m.service, "found": m.found,
                "url": m.url[:200] if m.url else None,
                "title": m.page_title[:100] if m.page_title else None,
                "similarity": round(m.similarity_score * 100) if m.similarity_score else None,
                "error": str(m.error)[:100] if m.error else None,
            }
            for m in result.reverse_search.matches
        ]}

    if result.ai_detection:
        ai = result.ai_detection
        out["ai_detection"] = {
            "overall": ai.overall_suspicion.value,
            "score": round(ai.ai_suspicion_score * 100),
            "services": [
                {
                    "service": s.service,
                    "verdict": s.verdict[:150] if s.verdict else None,
                    "probability": round(s.ai_probability * 100) if s.ai_probability is not None else None,
                    "error": str(s.error)[:100] if s.error else None,
                }
                for s in ai.service_results
            ],
        }

    return out

from flask import redirect, url_for

if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
    except:
        ip = "localhost"
    print(f"\n{'='*50}\n  PhotoCheck\n{'='*50}")
    print(f"  http://localhost:8080")
    print(f"  http://{ip}:8080  (mobile)")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
