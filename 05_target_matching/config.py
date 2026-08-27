import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

CONFIG_DIR = Path(__file__).resolve().parent.parent / 'configs'
DEFAULT_CONFIG_PATH = CONFIG_DIR / 'target_matching.yaml'


@dataclass
class TargetMatchingConfig:
    # Thresholds
    exact_fast_path: bool = True
    high_probability_threshold: float = 0.90
    probable_threshold: float = 0.70
    possible_threshold: float = 0.50

    # Feature Weights
    similarity_weight: float = 0.55
    ocr_confidence_weight: float = 0.15
    support_weight: float = 0.15
    grammar_weight: float = 0.10
    quality_weight: float = 0.05
    base_confusion_cost: float = 0.20

    # Alert Policies
    min_alert_class: str = 'HIGH_PROBABILITY'
    cooldown_seconds: float = 60.0
    deduplicate_by_track: bool = True
    exact_evidence_gate_required: bool = True
    min_exact_alert_confidence: float = 0.85
    min_exact_alert_support: int = 2

    # Watchlist & Indexing
    cache_enabled: bool = True
    max_candidate_shortlist: int = 100
    duplicate_policy: str = 'update'  # 'update' | 'reject'

    # Persistence
    db_backend: str = 'postgres'  # 'postgres' | 'sqlite'
    sqlite_db_path: str = ':memory:'

    @classmethod
    def from_yaml(cls, path: Optional[str] = None) -> 'TargetMatchingConfig':
        p = Path(path) if path else DEFAULT_CONFIG_PATH
        if not p.exists():
            return cls()

        with open(p, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        matching = data.get('matching', {})
        scoring = data.get('scoring', {})
        alerts = data.get('alerts', {})
        watchlist = data.get('watchlist', {})
        database = data.get('database', {})

        return cls(
            exact_fast_path=matching.get('exact_fast_path', True),
            high_probability_threshold=matching.get('high_probability_threshold', 0.90),
            probable_threshold=matching.get('probable_threshold', 0.70),
            possible_threshold=matching.get('possible_threshold', 0.50),
            similarity_weight=scoring.get('similarity_weight', 0.55),
            ocr_confidence_weight=scoring.get('ocr_confidence_weight', 0.15),
            support_weight=scoring.get('support_weight', 0.15),
            grammar_weight=scoring.get('grammar_weight', 0.10),
            quality_weight=scoring.get('quality_weight', 0.05),
            base_confusion_cost=scoring.get('base_confusion_cost', 0.20),
            min_alert_class=alerts.get('min_alert_class', 'HIGH_PROBABILITY'),
            cooldown_seconds=alerts.get('cooldown_seconds', 60.0),
            deduplicate_by_track=alerts.get('deduplicate_by_track', True),
            exact_evidence_gate_required=alerts.get('exact_evidence_gate_required', True),
            min_exact_alert_confidence=alerts.get('min_exact_alert_confidence', 0.85),
            min_exact_alert_support=alerts.get('min_exact_alert_support', 2),
            cache_enabled=watchlist.get('cache_enabled', True),
            max_candidate_shortlist=watchlist.get('max_candidate_shortlist', 100),
            duplicate_policy=watchlist.get('duplicate_policy', 'update'),
            db_backend=database.get('backend', 'postgres'),
            sqlite_db_path=database.get('sqlite_path', ':memory:')
        )
