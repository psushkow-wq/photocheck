"""
tests/test_pipeline.py — Integration tests for the analysis pipeline.

These tests run the full pipeline in "local" mode (no external APIs).
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline import run_pipeline
from core.models import AnalysisResult, TrustLevel


def _make_test_jpeg(tmp_path) -> Path:
    img = Image.new("RGB", (200, 200), color=(180, 120, 60))
    out = tmp_path / "sample.jpg"
    img.save(out, "JPEG", quality=85)
    return out


class TestPipeline:
    def test_local_run_completes(self, tmp_path):
        path = _make_test_jpeg(tmp_path)
        result = run_pipeline(
            image_path=str(path),
            mode="local",
            allow_external=False,
        )
        assert isinstance(result, AnalysisResult)
        assert result.completed is True

    def test_forensics_populated(self, tmp_path):
        path = _make_test_jpeg(tmp_path)
        result = run_pipeline(str(path), mode="local", allow_external=False)
        assert result.forensics is not None
        assert result.forensics.width == 200
        assert result.forensics.height == 200
        assert result.forensics.format in ("JPEG", "JPG")

    def test_hashes_populated(self, tmp_path):
        path = _make_test_jpeg(tmp_path)
        result = run_pipeline(str(path), mode="local", allow_external=False)
        assert result.hashes is not None
        assert len(result.hashes.md5) == 32

    def test_risk_score_computed(self, tmp_path):
        path = _make_test_jpeg(tmp_path)
        result = run_pipeline(str(path), mode="local", allow_external=False)
        assert result.risk_score is not None
        assert result.risk_score.overall_trust_level in TrustLevel.__members__.values()

    def test_nonexistent_file_returns_error(self, tmp_path):
        result = run_pipeline("/nonexistent/image.jpg", mode="local", allow_external=False)
        assert result.completed is False
        assert len(result.errors) > 0

    def test_unsupported_format_returns_error(self, tmp_path):
        bad = tmp_path / "file.txt"
        bad.write_text("not an image")
        result = run_pipeline(str(bad), mode="local", allow_external=False)
        assert result.completed is False
