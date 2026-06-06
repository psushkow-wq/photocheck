"""
PhotoAuth — Веб-сервис проверки подлинности фотографий.
"""

import base64
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)

# Путь к движку анализа
ENGINE_PATH = Path(__file__).parent.parent / "photo_authenticator"
sys.path.insert(0, str(ENGINE_PATH))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "photoauth-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

DB_PATH = Path(__file__).parent / "data" / "site.db"
DB_PATH.parent.mkdir(exist_ok=True)

UPLOAD_TMP = Path(tempfile.gettempdir()) / "photoauth_uploads"
UPLOAD_TMP.mkdir(exist_ok=True)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".bmp"}

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT,
            analyses_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            analysis_id TEXT,
            filename TEXT,
            trust_level TEXT,
            ai_score REAL,
            manipulation_score REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            ip TEXT,
            user_agent TEXT,
            user_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        );

        INSERT OR IGNORE INTO stats (key, value) VALUES
            ('total_visits', 0),
            ('total_analyses', 0),
            ('total_users', 0);
    """)
    conn.commit()
    conn.close()


init_db()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def increment_stat(key: str, amount: int = 1):
    try:
        conn = get_db()
        conn.execute("UPDATE stats SET value = value + ? WHERE key = ?", (amount, key))
        conn.commit()
        conn.close()
    except Exception:
        pass


def track_visit(path: str):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO visits (path, ip, user_agent, user_id) VALUES (?, ?, ?, ?)",
            (path, request.remote_addr,
             request.user_agent.string[:200],
             session.get("user_id"))
        )
        conn.commit()
        conn.close()
        increment_stat("total_visits")
    except Exception:
        pass


# ── Auth decorator ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Войдите в аккаунт для доступа к инструменту", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@app.before_request
def before_request():
    if request.path.startswith("/static"):
        return
    track_visit(request.path)


@app.route("/")
def index():
    conn = get_db()
    stats = {row["key"]: row["value"] for row in conn.execute("SELECT * FROM stats")}
    conn.close()
    user = None
    if "user_id" in session:
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        conn.close()
    return render_template("index.html", stats=stats, user=user)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("tool"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if not name or len(name) < 2:
            errors.append("Введите имя (минимум 2 символа)")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors.append("Введите корректный email")
        if len(password) < 6:
            errors.append("Пароль минимум 6 символов")
        if password != confirm:
            errors.append("Пароли не совпадают")

        if not errors:
            try:
                conn = get_db()
                conn.execute(
                    "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                    (email, hash_password(password), name)
                )
                conn.commit()
                user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
                conn.close()
                session["user_id"] = user_id
                session["user_name"] = name
                increment_stat("total_users")
                flash(f"Добро пожаловать, {name}! 🎉", "success")
                return redirect(url_for("tool"))
            except sqlite3.IntegrityError:
                errors.append("Этот email уже зарегистрирован")

        for e in errors:
            flash(e, "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("tool"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password_hash = ?",
            (email, hash_password(password))
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            conn = get_db()
            conn.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user["id"],))
            conn.commit()
            conn.close()
            flash(f"Добро пожаловать, {user['name']}!", "success")
            next_url = request.args.get("next", url_for("tool"))
            return redirect(next_url)
        else:
            flash("Неверный email или пароль", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("index"))


@app.route("/tool")
@login_required
def tool():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    recent = conn.execute(
        "SELECT * FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("tool.html", user=user, recent=recent)


@app.route("/analyze", methods=["POST"])
@login_required
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "Файл не загружен"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        return jsonify({"error": f"Неподдерживаемый формат: {suffix}"}), 400

    mode = request.form.get("mode", "fast")
    allow_external = request.form.get("allow_external", "true") == "true"

    tmp_path = UPLOAD_TMP / f"{uuid.uuid4()}{suffix}"
    file.save(str(tmp_path))

    try:
        from config import Config, setup_logging
        from core.pipeline import run_pipeline
        setup_logging()

        result = run_pipeline(str(tmp_path), mode=mode, allow_external=allow_external)
        data = _serialize_result(result)

        # Save to DB
        conn = get_db()
        conn.execute(
            """INSERT INTO analyses (user_id, analysis_id, filename, trust_level, ai_score, manipulation_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"], result.analysis_id, file.filename,
                data.get("risk", {}).get("level", "unknown"),
                data.get("ai_detection", {}).get("score", 0) / 100 if data.get("ai_detection") else 0,
                data.get("forensics", {}).get("manipulation_score", 0),
            )
        )
        conn.execute("UPDATE users SET analyses_count = analyses_count + 1 WHERE id = ?", (session["user_id"],))
        conn.commit()
        conn.close()
        increment_stat("total_analyses")

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.route("/ela_image")
@login_required
def ela_image():
    path = request.args.get("path", "")
    if path and Path(path).exists():
        return send_file(path, mimetype="image/jpeg")
    return "", 404


@app.route("/profile")
@login_required
def profile():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    analyses = conn.execute(
        "SELECT * FROM analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("profile.html", user=user, analyses=analyses)


@app.route("/admin/stats")
def admin_stats():
    # Простая страница статистики (в продакшене добавить пароль)
    secret = request.args.get("key", "")
    if secret != os.environ.get("ADMIN_KEY", "admin123"):
        return "Access denied", 403

    conn = get_db()
    stats = {row["key"]: row["value"] for row in conn.execute("SELECT * FROM stats")}
    users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    analyses_count = conn.execute("SELECT COUNT(*) as c FROM analyses").fetchone()["c"]

    visits_today = conn.execute(
        "SELECT COUNT(*) as c FROM visits WHERE date(created_at) = date('now')"
    ).fetchone()["c"]

    visits_week = conn.execute(
        "SELECT COUNT(*) as c FROM visits WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()["c"]

    recent_users = conn.execute(
        "SELECT name, email, created_at, analyses_count FROM users ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    top_pages = conn.execute(
        "SELECT path, COUNT(*) as cnt FROM visits GROUP BY path ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    conn.close()

    return render_template("admin_stats.html",
        stats=stats, users_count=users_count,
        analyses_count=analyses_count,
        visits_today=visits_today, visits_week=visits_week,
        recent_users=recent_users, top_pages=top_pages)


# ── Serialization (same as web_app.py) ────────────────────────────────────────

def _serialize_result(result) -> dict:
    from core.models import TrustLevel, AISuspicion

    out = {
        "analysis_id": result.analysis_id,
        "completed": result.completed,
        "errors": result.errors,
        "risk": None, "metadata": None, "hashes": None,
        "forensics": None, "reverse_search": None, "ai_detection": None,
    }

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
            "datetime_modified": m.datetime_modified, "lens_model": m.lens_model,
            "aperture": m.aperture, "shutter_speed": m.shutter_speed,
            "iso": m.iso, "focal_length": m.focal_length,
            "editing_software": m.editing_software_detected,
            "warnings": m.warnings,
            "gps": {
                "latitude": m.gps.latitude, "longitude": m.gps.longitude,
                "altitude": m.gps.altitude, "address": m.gps.reverse_geocode_address,
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
            "color_mode": f.color_mode, "file_size_kb": round(f.file_size_bytes / 1024, 1),
            "jpeg_quality": f.jpeg_quality_estimate,
            "manipulation_flags": f.manipulation_flags,
            "manipulation_score": f.manipulation_score,
            "ela": {
                "suspicious_percent": round(f.ela.suspicious_regions_percent, 1),
                "max_diff": round(f.ela.max_difference, 1),
                "mean_diff": round(f.ela.mean_difference, 2),
                "notes": f.ela.notes, "image_path": ela_path,
            } if f.ela else None,
        }

    if result.reverse_search:
        rs = result.reverse_search
        out["reverse_search"] = {
            "earliest_url": rs.earliest_found_url,
            "matches": [
                {
                    "service": m.service, "found": m.found,
                    "url": m.url[:200] if m.url else None,
                    "title": m.page_title[:100] if m.page_title else None,
                    "similarity": round(m.similarity_score * 100) if m.similarity_score else None,
                    "error": str(m.error)[:100] if m.error else None,
                }
                for m in rs.matches
            ],
        }

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
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    print(f"\n{'='*50}")
    print(f"  PhotoAuth Site")
    print(f"{'='*50}")
    print(f"  Компьютер:  http://localhost:8080")
    print(f"  Телефон:    http://{local_ip}:8080")
    print(f"  Статистика: http://localhost:8080/admin/stats?key=admin123")
    print(f"{'='*50}\n")

    app.run(host="0.0.0.0", port=8080, debug=False)
