"""
config.py — Centralized configuration loader.
Reads .env file and provides typed access to all settings.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).parent
load_dotenv(_ROOT / ".env")


class Config:
    # --- API Keys ---
    TINEYE_API_KEY: str = os.getenv("TINEYE_API_KEY", "")
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    BING_SEARCH_KEY: str = os.getenv("BING_SEARCH_KEY", "")
    HIVE_API_KEY: str = os.getenv("HIVE_API_KEY", "")
    SIGHTENGINE_API_USER: str = os.getenv("SIGHTENGINE_API_USER", "")
    SIGHTENGINE_API_SECRET: str = os.getenv("SIGHTENGINE_API_SECRET", "")
    ILLUMINARTY_API_KEY: str = os.getenv("ILLUMINARTY_API_KEY", "")
    OPENCAGE_API_KEY: str = os.getenv("OPENCAGE_API_KEY", "")

    # --- App settings ---
    DEFAULT_MODE: str = os.getenv("DEFAULT_MODE", "fast")
    ALLOW_EXTERNAL_DEFAULT: bool = os.getenv("ALLOW_EXTERNAL_DEFAULT", "false").lower() == "true"
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    DB_PATH: Path = _ROOT / os.getenv("DB_PATH", "data/history.sqlite")

    # --- Derived ---
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".bmp"}

    @classmethod
    def has_tineye(cls) -> bool:
        return bool(cls.TINEYE_API_KEY)

    @classmethod
    def has_serpapi(cls) -> bool:
        return bool(cls.SERPAPI_KEY)

    @classmethod
    def has_bing(cls) -> bool:
        return bool(cls.BING_SEARCH_KEY)

    @classmethod
    def has_hive(cls) -> bool:
        return bool(cls.HIVE_API_KEY)

    @classmethod
    def has_sightengine(cls) -> bool:
        return bool(cls.SIGHTENGINE_API_USER and cls.SIGHTENGINE_API_SECRET)

    @classmethod
    def has_illuminarty(cls) -> bool:
        return bool(cls.ILLUMINARTY_API_KEY)

    @classmethod
    def has_opencage(cls) -> bool:
        return bool(cls.OPENCAGE_API_KEY)

    @classmethod
    def available_apis(cls) -> list[str]:
        """Return list of configured API names."""
        apis = []
        if cls.has_tineye():
            apis.append("TinEye")
        if cls.has_serpapi():
            apis.append("SerpAPI (Google Lens / Yandex)")
        if cls.has_bing():
            apis.append("Bing Visual Search")
        if cls.has_hive():
            apis.append("Hive AI Detection")
        if cls.has_sightengine():
            apis.append("Sightengine AI Detection")
        if cls.has_illuminarty():
            apis.append("Illuminarty AI Detection")
        return apis


# Configure logging once here
def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


setup_logging()
