"""Configuration for the bounded Priority 6 appearance fallback."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "configs" / "reid.yaml"


@dataclass(frozen=True)
class ReIDConfig:
    """Small, explicit configuration surface for the P6 fallback."""

    enabled: bool = True
    model_name: str = "mobilenet_v3_small_imagenet"
    model_version: str = "torchvision-0.20.1"
    checkpoint_url: str = "https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth"
    checkpoint_sha256: str = ""
    checkpoint_path: Optional[str] = None
    allow_checkpoint_download: bool = True
    device: str = "auto"
    input_width: int = 224
    input_height: int = 224
    embedding_dimension: int = 576
    top_k_crops_per_track: int = 5
    minimum_crop_width: int = 32
    minimum_crop_height: int = 32
    minimum_crop_quality: float = 0.0
    plate_region_masked_for_reid: bool = True
    plate_mask_padding_fraction: float = 0.15
    gallery_max_tracks: int = 10000
    gallery_ttl_seconds: float = 3600.0
    search_time_window_seconds: float = 3600.0
    minimum_similarity_for_support: float = 0.90
    minimum_similarity_for_review: float = 0.80
    maximum_false_match_rate: float = 0.01
    review_only: bool = True
    require_class_compatibility: bool = True

    @classmethod
    def from_yaml(cls, path: Optional[str] = None) -> "ReIDConfig":
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls()

        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        values = dict(data.get("reid", data))
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in values.items() if key in known})
