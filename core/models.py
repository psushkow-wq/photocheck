"""
core/models.py — Typed data models for analysis results.
All modules return these standardized structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class TrustLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class AISuspicion(str, Enum):
    NONE = "Признаков AI-генерации не обнаружено"
    WEAK = "Слабые признаки AI-генерации"
    MODERATE = "Умеренные признаки AI-генерации"
    STRONG = "Сильные признаки AI-генерации"
    CONTRADICTORY = "Противоречивые результаты AI-анализа"
    INSUFFICIENT = "Недостаточно данных для AI-анализа"


@dataclass
class GPSInfo:
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    gps_timestamp: Optional[str] = None
    openstreetmap_url: str = ""
    google_maps_url: str = ""
    reverse_geocode_address: Optional[str] = None

    def __post_init__(self):
        self.openstreetmap_url = (
            f"https://www.openstreetmap.org/?mlat={self.latitude}&mlon={self.longitude}&zoom=15"
        )
        self.google_maps_url = (
            f"https://maps.google.com/?q={self.latitude},{self.longitude}"
        )


@dataclass
class MetadataResult:
    raw_exif: dict = field(default_factory=dict)
    raw_iptc: dict = field(default_factory=dict)
    raw_xmp: dict = field(default_factory=dict)
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None
    datetime_original: Optional[str] = None
    datetime_modified: Optional[str] = None
    orientation: Optional[str] = None
    lens_model: Optional[str] = None
    focal_length: Optional[str] = None
    aperture: Optional[str] = None
    shutter_speed: Optional[str] = None
    iso: Optional[str] = None
    gps: Optional[GPSInfo] = None
    has_thumbnail: bool = False
    thumbnail_mismatch: bool = False
    editing_software_detected: Optional[str] = None  # e.g. "Adobe Photoshop CS6"
    warnings: list[str] = field(default_factory=list)
    # Confidence: 0.0 = no metadata, 1.0 = full rich metadata
    confidence_score: float = 0.0


@dataclass
class HashResult:
    phash: str = ""
    dhash: str = ""
    ahash: str = ""
    whash: str = ""
    md5: str = ""
    sha256: str = ""
    local_duplicate_found: bool = False
    local_duplicate_path: Optional[str] = None
    local_similarity_score: float = 0.0


@dataclass
class ELAResult:
    ela_image_path: Optional[str] = None  # path to saved ELA visualization
    max_difference: float = 0.0
    mean_difference: float = 0.0
    suspicious_regions_percent: float = 0.0
    recompression_detected: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class ForensicsResult:
    file_size_bytes: int = 0
    width: int = 0
    height: int = 0
    format: str = ""
    color_mode: str = ""
    color_profile: Optional[str] = None
    has_alpha: bool = False
    jpeg_quality_estimate: Optional[int] = None
    ela: Optional[ELAResult] = None
    ocr_text: Optional[str] = None
    manipulation_score: float = 0.0  # 0.0–1.0
    manipulation_flags: list[str] = field(default_factory=list)


@dataclass
class ReverseSearchMatch:
    service: str = ""
    found: bool = False
    url: Optional[str] = None
    page_title: Optional[str] = None
    first_seen_date: Optional[str] = None
    similarity_score: Optional[float] = None
    match_type: str = ""  # "exact" / "similar" / "visual"
    thumbnail_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ReverseSearchResult:
    matches: list[ReverseSearchMatch] = field(default_factory=list)
    checked_services: list[str] = field(default_factory=list)
    skipped_services: list[str] = field(default_factory=list)
    earliest_found_date: Optional[str] = None
    earliest_found_url: Optional[str] = None
    internet_provenance_score: float = 0.0  # 0.0 = unknown, 1.0 = widely known


@dataclass
class AIServiceResult:
    service: str = ""
    ai_probability: Optional[float] = None  # 0.0–1.0 if available
    verdict: str = ""  # raw verdict from service
    details: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class AIDetectionResult:
    service_results: list[AIServiceResult] = field(default_factory=list)
    overall_suspicion: AISuspicion = AISuspicion.INSUFFICIENT
    ai_suspicion_score: float = 0.0  # 0.0–1.0
    local_heuristics_flags: list[str] = field(default_factory=list)


@dataclass
class RiskScore:
    """Multi-dimensional risk assessment."""
    internet_provenance_score: float = 0.0   # How well-known is this image online
    metadata_confidence_score: float = 0.0   # How complete/consistent are metadata
    ai_suspicion_score: float = 0.0          # How likely AI-generated
    manipulation_suspicion_score: float = 0.0  # How likely edited/manipulated
    geolocation_confidence_score: float = 0.0  # How reliable are geodata

    overall_trust_level: TrustLevel = TrustLevel.UNKNOWN
    overall_summary: str = ""
    red_flags: list[str] = field(default_factory=list)
    authenticity_arguments: list[str] = field(default_factory=list)
    what_was_checked: list[str] = field(default_factory=list)
    what_was_skipped: list[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Top-level container for a complete analysis run."""
    image_path: str = ""
    analysis_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    mode: str = "fast"  # fast / full / local

    metadata: Optional[MetadataResult] = None
    hashes: Optional[HashResult] = None
    forensics: Optional[ForensicsResult] = None
    reverse_search: Optional[ReverseSearchResult] = None
    ai_detection: Optional[AIDetectionResult] = None
    risk_score: Optional[RiskScore] = None

    log_entries: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    completed: bool = False
