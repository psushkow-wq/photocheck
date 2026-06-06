"""
data/database.py — SQLite persistence for analysis history.

Stores a compact record of each analysis run:
  - image path, timestamp, mode
  - perceptual hashes (for duplicate detection)
  - trust level
  - JSON blob of the full result

Also provides find_similar_hash() used by hashing.py to detect
locally-seen near-duplicate images.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

import imagehash

from config import Config

logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    db_path = Config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT    UNIQUE NOT NULL,
            image_path  TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            mode        TEXT    NOT NULL,
            phash       TEXT,
            dhash       TEXT,
            trust_level TEXT,
            result_json TEXT
        )
    """)
    conn.commit()


def save_result_to_db(result) -> None:
    """Persist an AnalysisResult to the SQLite database."""
    try:
        conn = _get_connection()
        _ensure_schema(conn)

        phash = result.hashes.phash if result.hashes else None
        dhash = result.hashes.dhash if result.hashes else None
        trust = result.risk_score.overall_trust_level.value if result.risk_score else None

        def _default(obj):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            if hasattr(obj, "value"):
                return obj.value
            return str(obj)

        result_json = json.dumps(result, default=_default, ensure_ascii=False)

        conn.execute("""
            INSERT OR REPLACE INTO analysis_history
                (analysis_id, image_path, timestamp, mode, phash, dhash, trust_level, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.analysis_id,
            result.image_path,
            result.timestamp,
            result.mode,
            phash,
            dhash,
            trust,
            result_json,
        ))
        conn.commit()
        conn.close()
        logger.debug(f"Saved analysis {result.analysis_id} to DB")
    except Exception as e:
        logger.warning(f"DB save error: {e}")


def find_similar_hash(phash_str: str, threshold: int = 8) -> Optional[dict]:
    """
    Search history for a perceptually similar image.

    Returns dict with 'image_path', 'similarity' (0.0–1.0), 'analysis_id'
    or None if no match found.
    """
    try:
        conn = _get_connection()
        _ensure_schema(conn)

        target = imagehash.hex_to_hash(phash_str)

        rows = conn.execute(
            "SELECT analysis_id, image_path, phash FROM analysis_history WHERE phash IS NOT NULL"
        ).fetchall()
        conn.close()

        best = None
        best_distance = threshold + 1

        for row in rows:
            try:
                candidate = imagehash.hex_to_hash(row["phash"])
                distance = target - candidate
                if distance <= threshold and distance < best_distance:
                    best_distance = distance
                    best = {
                        "analysis_id": row["analysis_id"],
                        "image_path": row["image_path"],
                        "similarity": 1.0 - (distance / 64.0),
                    }
            except Exception:
                continue

        return best
    except Exception as e:
        logger.warning(f"DB hash lookup error: {e}")
        return None


def get_history(limit: int = 50) -> list[dict]:
    """Return recent analysis records for the history view."""
    try:
        conn = _get_connection()
        _ensure_schema(conn)
        rows = conn.execute("""
            SELECT analysis_id, image_path, timestamp, mode, trust_level
            FROM analysis_history
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"DB history error: {e}")
        return []


def clear_history() -> int:
    """Delete all history records. Returns number of deleted rows."""
    try:
        conn = _get_connection()
        _ensure_schema(conn)
        cur = conn.execute("DELETE FROM analysis_history")
        conn.commit()
        conn.close()
        return cur.rowcount
    except Exception as e:
        logger.warning(f"DB clear error: {e}")
        return 0
