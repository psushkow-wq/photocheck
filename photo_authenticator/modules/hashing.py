"""
modules/hashing.py — Computes perceptual and cryptographic hashes.

Perceptual hashes (pHash, dHash, aHash, wHash) allow finding visually
similar images even after minor edits. Cryptographic hashes identify
exact duplicates. Results are compared against the local SQLite history.
"""

import hashlib
import logging
from pathlib import Path

import imagehash
from PIL import Image

from core.models import HashResult
from data.database import find_similar_hash

logger = logging.getLogger(__name__)

# Maximum hamming distance to consider two images "similar"
SIMILARITY_THRESHOLD = 8  # out of 64 bits


def compute_hashes(image_path: str) -> HashResult:
    result = HashResult()
    path = Path(image_path)

    # ── Cryptographic hashes ─────────────────────────────────────────────────
    data = path.read_bytes()
    result.md5 = hashlib.md5(data).hexdigest()
    result.sha256 = hashlib.sha256(data).hexdigest()

    # ── Perceptual hashes ────────────────────────────────────────────────────
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            result.phash = str(imagehash.phash(img))
            result.dhash = str(imagehash.dhash(img))
            result.ahash = str(imagehash.average_hash(img))
            result.whash = str(imagehash.whash(img))
    except Exception as e:
        logger.warning(f"Perceptual hash error: {e}")

    # ── Compare against local history ────────────────────────────────────────
    try:
        match = find_similar_hash(result.phash, threshold=SIMILARITY_THRESHOLD)
        if match:
            result.local_duplicate_found = True
            result.local_duplicate_path = match["image_path"]
            result.local_similarity_score = match["similarity"]
            logger.info(
                f"Local duplicate found: {match['image_path']} "
                f"(similarity {match['similarity']:.2f})"
            )
    except Exception as e:
        logger.warning(f"DB lookup failed: {e}")

    return result
