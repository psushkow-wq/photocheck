"""
modules/metadata_extractor.py — Extracts EXIF, IPTC, XMP metadata and GPS.

Uses Pillow as primary method (zero deps beyond Pillow).
Falls back to piexif for richer EXIF detail.
ExifTool (via subprocess) used if installed for maximum coverage.
"""

import logging
import subprocess
import json
import struct
from pathlib import Path
from typing import Optional

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from core.models import MetadataResult, GPSInfo

logger = logging.getLogger(__name__)

# Known editing software substrings (case-insensitive)
EDITING_SOFTWARE_MARKERS = [
    "photoshop", "lightroom", "gimp", "canva", "pixelmator",
    "affinity", "capture one", "luminar", "topaz", "snapseed",
    "stable diffusion", "midjourney", "dall-e", "firefly",
    "comfyui", "automatic1111", "invoke", "leonardo",
]


def extract_metadata(image_path: str) -> MetadataResult:
    result = MetadataResult()
    path = Path(image_path)

    # ── Primary: Pillow ──────────────────────────────────────────────────────
    try:
        with Image.open(path) as img:
            _extract_pillow(img, result)
    except Exception as e:
        logger.warning(f"Pillow metadata extraction error: {e}")
        result.warnings.append(f"Pillow не смог прочитать метаданные: {e}")

    # ── Secondary: ExifTool via subprocess ───────────────────────────────────
    try:
        _extract_exiftool(str(path), result)
    except FileNotFoundError:
        logger.debug("exiftool not installed — skipping")
    except Exception as e:
        logger.warning(f"ExifTool extraction error: {e}")

    # ── Compute confidence score ─────────────────────────────────────────────
    result.confidence_score = _compute_confidence(result)

    # ── Warnings ─────────────────────────────────────────────────────────────
    if result.confidence_score == 0.0:
        result.warnings.append(
            "Метаданные полностью отсутствуют. Это может быть нормой для изображений, "
            "загруженных через мессенджеры или соцсети — они часто удаляют EXIF."
        )
    if result.editing_software_detected:
        result.warnings.append(
            f"Обнаружен тег программы редактирования: «{result.editing_software_detected}». "
            "Это означает, что изображение обрабатывалось в редакторе, но не является "
            "доказательством фальсификации."
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pillow(img: Image.Image, result: MetadataResult) -> None:
    """Extract metadata using Pillow."""
    exif_data = img._getexif()  # returns dict or None
    if not exif_data:
        return

    decoded = {}
    gps_raw = {}

    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        if tag_name == "GPSInfo":
            for gps_tag, gps_val in value.items():
                gps_decoded_tag = GPSTAGS.get(gps_tag, str(gps_tag))
                gps_raw[gps_decoded_tag] = gps_val
        else:
            try:
                decoded[tag_name] = _safe_value(value)
            except Exception:
                decoded[tag_name] = repr(value)

    result.raw_exif = decoded

    # Map well-known fields
    result.camera_make = decoded.get("Make")
    result.camera_model = decoded.get("Model")
    result.software = decoded.get("Software")
    result.datetime_original = decoded.get("DateTimeOriginal") or decoded.get("DateTime")
    result.datetime_modified = decoded.get("DateTimeDigitized")
    result.lens_model = decoded.get("LensModel")
    result.aperture = decoded.get("FNumber") or decoded.get("ApertureValue")
    result.shutter_speed = decoded.get("ExposureTime") or decoded.get("ShutterSpeedValue")
    result.iso = decoded.get("ISOSpeedRatings")
    result.focal_length = decoded.get("FocalLength")
    result.orientation = decoded.get("Orientation")

    # Software detection
    _check_editing_software(result)

    # GPS
    if gps_raw:
        result.gps = _parse_gps(gps_raw)

    # Thumbnail presence
    try:
        raw = img.info.get("exif", b"")
        result.has_thumbnail = b"\xff\xd8\xff" in raw[6:]  # JPEG marker in EXIF
    except Exception:
        pass


def _extract_exiftool(image_path: str, result: MetadataResult) -> None:
    """Run exiftool and merge results."""
    proc = subprocess.run(
        ["exiftool", "-j", "-a", "-u", "-g", image_path],
        capture_output=True, text=True, timeout=15
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return

    data = json.loads(proc.stdout)
    if not data:
        return

    flat = data[0]  # exiftool returns a list
    # Merge IPTC and XMP
    result.raw_iptc = {k: v for k, v in flat.items() if k.startswith("IPTC")}
    result.raw_xmp = {k: v for k, v in flat.items() if k.startswith("XMP")}

    # Fill gaps not found by Pillow
    if not result.camera_make:
        result.camera_make = flat.get("Make")
    if not result.camera_model:
        result.camera_model = flat.get("Model")
    if not result.software:
        result.software = flat.get("Software")
    if not result.datetime_original:
        result.datetime_original = flat.get("DateTimeOriginal")
    if not result.gps:
        lat = flat.get("GPSLatitude")
        lon = flat.get("GPSLongitude")
        if lat and lon:
            try:
                result.gps = GPSInfo(latitude=float(lat), longitude=float(lon))
            except (ValueError, TypeError):
                pass

    _check_editing_software(result)


def _check_editing_software(result: MetadataResult) -> None:
    """Detect editing software from software tag."""
    sw = (result.software or "").lower()
    for marker in EDITING_SOFTWARE_MARKERS:
        if marker in sw:
            result.editing_software_detected = result.software
            break


def _parse_gps(gps_raw: dict) -> Optional[GPSInfo]:
    """Convert Pillow GPS dict to GPSInfo."""
    try:
        lat = _dms_to_decimal(
            gps_raw.get("GPSLatitude"),
            gps_raw.get("GPSLatitudeRef", "N")
        )
        lon = _dms_to_decimal(
            gps_raw.get("GPSLongitude"),
            gps_raw.get("GPSLongitudeRef", "E")
        )
        if lat is None or lon is None:
            return None
        alt_raw = gps_raw.get("GPSAltitude")
        alt = None
        if alt_raw:
            try:
                alt = float(alt_raw[0]) / float(alt_raw[1]) if isinstance(alt_raw, tuple) else float(alt_raw)
            except Exception:
                pass
        return GPSInfo(latitude=lat, longitude=lon, altitude=alt)
    except Exception as e:
        logger.warning(f"GPS parse error: {e}")
        return None


def _dms_to_decimal(dms, ref: str) -> Optional[float]:
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    if dms is None:
        return None
    try:
        if isinstance(dms, (int, float)):
            val = float(dms)
        else:
            d = float(dms[0][0]) / float(dms[0][1]) if isinstance(dms[0], tuple) else float(dms[0])
            m = float(dms[1][0]) / float(dms[1][1]) if isinstance(dms[1], tuple) else float(dms[1])
            s = float(dms[2][0]) / float(dms[2][1]) if isinstance(dms[2], tuple) else float(dms[2])
            val = d + m / 60 + s / 3600
        if str(ref).upper() in ("S", "W"):
            val = -val
        return val
    except Exception as e:
        logger.debug(f"DMS conversion error: {e}")
        return None


def _safe_value(val) -> object:
    """Convert Pillow IFDRational and bytes to JSON-serializable types."""
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        return float(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, tuple):
        return [_safe_value(v) for v in val]
    return val


def _compute_confidence(result: MetadataResult) -> float:
    """0.0–1.0 based on how much metadata is present."""
    score = 0.0
    weights = {
        "camera_make": 0.15,
        "camera_model": 0.15,
        "datetime_original": 0.20,
        "iso": 0.10,
        "shutter_speed": 0.10,
        "aperture": 0.10,
        "software": 0.05,
        "lens_model": 0.05,
    }
    for attr, weight in weights.items():
        if getattr(result, attr):
            score += weight
    if result.gps:
        score += 0.10
    return min(score, 1.0)
