"""
tests/test_metadata.py — Unit tests for metadata extraction.

Run with:  pytest tests/
"""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image
from modules.metadata_extractor import (
    extract_metadata,
    _dms_to_decimal,
    _compute_confidence,
)
from core.models import MetadataResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_jpeg(tmp_path, with_exif: bool = False) -> Path:
    """Create a minimal JPEG file for testing."""
    img = Image.new("RGB", (100, 100), color=(128, 64, 32))
    out = tmp_path / "test.jpg"
    if with_exif:
        import piexif
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"TestMake",
                piexif.ImageIFD.Model: b"TestModel",
                piexif.ImageIFD.Software: b"TestSoftware 1.0",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2023:06:15 12:00:00",
                piexif.ExifIFD.ISOSpeedRatings: 200,
            },
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(out, "JPEG", exif=exif_bytes)
    else:
        img.save(out, "JPEG")
    return out


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDmsConversion:
    def test_north(self):
        dms = ((48, 1), (51, 1), (29, 1))  # 48°51'29" N
        val = _dms_to_decimal(dms, "N")
        assert abs(val - 48.858) < 0.01

    def test_south(self):
        dms = ((33, 1), (52, 1), (0, 1))  # 33°52' S
        val = _dms_to_decimal(dms, "S")
        assert val < 0

    def test_west(self):
        dms = ((2, 1), (21, 1), (0, 1))
        val = _dms_to_decimal(dms, "W")
        assert val < 0

    def test_none_input(self):
        assert _dms_to_decimal(None, "N") is None


class TestMetadataExtraction:
    def test_no_exif_returns_result(self, tmp_path):
        path = _make_jpeg(tmp_path, with_exif=False)
        result = extract_metadata(str(path))
        assert isinstance(result, MetadataResult)
        assert result.confidence_score == 0.0
        # Should warn about missing metadata
        assert any("отсутствуют" in w for w in result.warnings)

    def test_with_exif_populates_fields(self, tmp_path):
        try:
            import piexif
        except ImportError:
            pytest.skip("piexif not installed")
        path = _make_jpeg(tmp_path, with_exif=True)
        result = extract_metadata(str(path))
        assert result.camera_make == "TestMake"
        assert result.camera_model == "TestModel"
        assert result.confidence_score > 0.0

    def test_missing_file_raises(self):
        with pytest.raises(Exception):
            extract_metadata("/nonexistent/path/image.jpg")


class TestConfidenceScore:
    def test_empty_result_zero(self):
        r = MetadataResult()
        assert _compute_confidence(r) == 0.0

    def test_full_result_near_one(self):
        r = MetadataResult(
            camera_make="Sony",
            camera_model="A7 IV",
            datetime_original="2023:01:01 12:00:00",
            iso="800",
            shutter_speed="1/250",
            aperture="f/2.8",
            lens_model="FE 24-70mm",
        )
        score = _compute_confidence(r)
        assert score >= 0.7
