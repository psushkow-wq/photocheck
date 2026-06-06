"""
tests/test_hashing.py — Unit tests for image hashing.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.hashing import compute_hashes
from core.models import HashResult


def _make_png(tmp_path, color=(100, 150, 200)) -> Path:
    img = Image.new("RGB", (64, 64), color=color)
    out = tmp_path / "test.png"
    img.save(out, "PNG")
    return out


class TestHashing:
    def test_returns_hashresult(self, tmp_path):
        path = _make_png(tmp_path)
        result = compute_hashes(str(path))
        assert isinstance(result, HashResult)

    def test_hashes_are_strings(self, tmp_path):
        path = _make_png(tmp_path)
        result = compute_hashes(str(path))
        assert isinstance(result.phash, str) and len(result.phash) > 0
        assert isinstance(result.md5, str) and len(result.md5) == 32
        assert isinstance(result.sha256, str) and len(result.sha256) == 64

    def test_different_images_different_hashes(self, tmp_path):
        p1 = _make_png(tmp_path / "a.png", color=(10, 20, 30))
        p2 = _make_png(tmp_path / "b.png", color=(200, 210, 220))
        r1 = compute_hashes(str(p1))
        r2 = compute_hashes(str(p2))
        assert r1.md5 != r2.md5
        assert r1.sha256 != r2.sha256

    def test_same_file_same_hash(self, tmp_path):
        path = _make_png(tmp_path)
        r1 = compute_hashes(str(path))
        r2 = compute_hashes(str(path))
        assert r1.md5 == r2.md5
        assert r1.phash == r2.phash
