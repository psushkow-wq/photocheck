"""
web_app.py — Flask веб-сервер для Photo Authenticator.
Запуск: python web_app.py
Открыть в браузере: http://localhost:5000
На телефоне в той же сети: http://<ip-компьютера>:5000
"""

import base64
import json
import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

# Добавляем путь к основному модулю
sys.path.insert(0, str(Path(__file__).parent.parent / "photo_authenticator"))

from config import Config, setup_logging
from core.pipeline import run_pipeline
from core.models import TrustLevel, AISuspicion

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

UPLOAD_DIR = Path(tempfile.gettempdir()) / "photo_auth_web"
UPLOAD_DIR.mkdir(exist_ok=True)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "Пустое имя файла"}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix not in Config.SUPPORTED_FORMATS:
        return jsonify({"error": f"Неподдерживаемый формат: {suffix}"}), 400

    mode = request.form.get("mode", "fast")
    allow_external = request.form.get("allow_external", "true") == "true"

    # Сохраняем загруженный файл
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    file.save(str(tmp_path))

    try:
        result = run_pipeline(
            str(tmp_path),
            mode=mode,
            allow_external=allow_external,
        )
        return jsonify(_serialize_result(result, tmp_path))
    except Exception as e:
        logger.exception("Pipeline failed")
        return jsonify({"error": str(e)}), 500
    finally:
        # Удаляем загруженный файл (ELA остаётся в tempdir)
        if tmp_path.exists():
            tmp_path.unlink()


@app.route("/ela_image")
def ela_image():
    path = request.args.get("path", "")
    if path and Path(path).exists():
        return send_file(path, mimetype="image/jpeg")
    return "", 404


# ─── Serialization ────────────────────────────────────────────────────────────

def _serialize_result(result, original_path: Path) -> dict:
    out = {
        "analysis_id": result.analysis_id,
        "timestamp": result.timestamp,
        "mode": result.mode,
        "completed": result.completed,
        "errors": result.errors,
        "risk": None,
        "metadata": None,
        "hashes": None,
        "forensics": None,
        "reverse_search": None,
        "ai_detection": None,
    }

    # Risk score
    if result.risk_score:
        rs = result.risk_score
        trust_labels = {
            TrustLevel.HIGH:    ("🟢 Высокий уровень доверия", "high"),
            TrustLevel.MEDIUM:  ("🟡 Средний уровень доверия", "medium"),
            TrustLevel.LOW:     ("🔴 Низкий уровень доверия",  "low"),
            TrustLevel.UNKNOWN: ("⚪ Не определён",             "unknown"),
        }
        label, level = trust_labels.get(rs.overall_trust_level, ("⚪", "unknown"))
        out["risk"] = {
            "level": level,
            "label": label,
            "internet_provenance": round(rs.internet_provenance_score * 100),
            "metadata_confidence": round(rs.metadata_confidence_score * 100),
            "ai_suspicion": round(rs.ai_suspicion_score * 100),
            "manipulation_suspicion": round(rs.manipulation_suspicion_score * 100),
            "geolocation_confidence": round(rs.geolocation_confidence_score * 100),
            "red_flags": rs.red_flags,
            "authenticity_arguments": rs.authenticity_arguments,
            "what_was_checked": rs.what_was_checked,
            "what_was_skipped": rs.what_was_skipped,
        }

    # Metadata
    if result.metadata:
        m = result.metadata
        out["metadata"] = {
            "camera_make": m.camera_make,
            "camera_model": m.camera_model,
            "software": m.software,
            "datetime_original": m.datetime_original,
            "datetime_modified": m.datetime_modified,
            "lens_model": m.lens_model,
            "aperture": m.aperture,
            "shutter_speed": m.shutter_speed,
            "iso": m.iso,
            "focal_length": m.focal_length,
            "editing_software": m.editing_software_detected,
            "warnings": m.warnings,
            "confidence": round(m.confidence_score * 100),
            "gps": None,
        }
        if m.gps:
            out["metadata"]["gps"] = {
                "latitude": m.gps.latitude,
                "longitude": m.gps.longitude,
                "altitude": m.gps.altitude,
                "address": m.gps.reverse_geocode_address,
                "osm_url": m.gps.openstreetmap_url,
                "gmaps_url": m.gps.google_maps_url,
            }

    # Hashes
    if result.hashes:
        h = result.hashes
        out["hashes"] = {
            "phash": h.phash,
            "md5": h.md5,
            "sha256": h.sha256,
            "duplicate_found": h.local_duplicate_found,
            "duplicate_path": h.local_duplicate_path,
            "duplicate_similarity": round(h.local_similarity_score * 100) if h.local_similarity_score else 0,
        }

    # Forensics
    if result.forensics:
        f = result.forensics
        ela_path = None
        if f.ela and f.ela.ela_image_path and Path(f.ela.ela_image_path).exists():
            ela_path = f.ela.ela_image_path

        out["forensics"] = {
            "format": f.format,
            "width": f.width,
            "height": f.height,
            "color_mode": f.color_mode,
            "file_size_kb": round(f.file_size_bytes / 1024, 1),
            "jpeg_quality": f.jpeg_quality_estimate,
            "manipulation_flags": f.manipulation_flags,
            "ela": None,
        }
        if f.ela:
            out["forensics"]["ela"] = {
                "suspicious_percent": round(f.ela.suspicious_regions_percent, 1),
                "max_diff": round(f.ela.max_difference, 1),
                "mean_diff": round(f.ela.mean_difference, 2),
                "notes": f.ela.notes,
                "image_path": ela_path,
            }

    # Reverse search
    if result.reverse_search:
        rs = result.reverse_search
        out["reverse_search"] = {
            "earliest_url": rs.earliest_found_url,
            "earliest_date": rs.earliest_found_date,
            "matches": [
                {
                    "service": m.service,
                    "found": m.found,
                    "url": m.url[:200] if m.url else None,
                    "title": m.page_title[:100] if m.page_title else None,
                    "similarity": round(m.similarity_score * 100) if m.similarity_score else None,
                    "match_type": m.match_type,
                    "error": str(m.error)[:100] if m.error else None,
                }
                for m in rs.matches
            ],
        }

    # AI detection
    if result.ai_detection:
        ai = result.ai_detection
        out["ai_detection"] = {
            "overall": ai.overall_suspicion.value,
            "score": round(ai.ai_suspicion_score * 100),
            "heuristics": ai.local_heuristics_flags,
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


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Photo Authenticator — Web версия")
    print("="*50)
    print(f"  Открыть на этом компьютере:")
    print(f"  http://localhost:5000")
    print(f"\n  На телефоне (в той же Wi-Fi сети):")

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"  http://{local_ip}:5000")
    except Exception:
        print(f"  (узнайте IP компьютера в настройках Wi-Fi)")

    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
