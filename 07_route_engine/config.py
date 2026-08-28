from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / 'configs' / 'route_engine.yaml'


@dataclass
class RouteEngineConfig:
    """Configuration class for SentinelTrack Priority 7 Route / GIS Engine."""
    # Timing
    large_gap_seconds: float = 3600.0
    low_quality_tolerance_seconds: float = 60.0
    clock_skew_tolerance_seconds: float = 5.0

    # Feasibility
    urban_soft_speed_kmh: float = 90.0
    highway_soft_speed_kmh: float = 140.0
    hard_max_speed_kmh: float = 220.0
    dwell_speed_threshold_kmh: float = 5.0

    # Trajectory
    min_match_score: float = 0.60
    investigation_mode: bool = False
    max_candidate_sightings: int = 500
    max_alternative_paths: int = 3
    ambiguity_margin: float = 0.08
    collapse_same_camera_dwell: bool = True

    # Spatial
    default_nearby_radius_m: float = 5000.0
    max_nearby_radius_m: float = 50000.0

    # Confidence weights (sum = 1.0)
    identity_weight: float = 0.40
    timing_weight: float = 0.20
    spatial_weight: float = 0.15
    feasibility_weight: float = 0.15
    dominance_weight: float = 0.10

    # GeoJSON
    decimal_precision: int = 6

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> 'RouteEngineConfig':
        p = path or CONFIG_PATH
        if not p.exists():
            return cls()

        with open(p, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}

        cfg = cls()
        t = raw.get('timing', {})
        if 'large_gap_seconds' in t: cfg.large_gap_seconds = float(t['large_gap_seconds'])
        if 'low_quality_tolerance_seconds' in t: cfg.low_quality_tolerance_seconds = float(t['low_quality_tolerance_seconds'])
        if 'clock_skew_tolerance_seconds' in t: cfg.clock_skew_tolerance_seconds = float(t['clock_skew_tolerance_seconds'])

        f_cfg = raw.get('feasibility', {})
        if 'urban_soft_speed_kmh' in f_cfg: cfg.urban_soft_speed_kmh = float(f_cfg['urban_soft_speed_kmh'])
        if 'highway_soft_speed_kmh' in f_cfg: cfg.highway_soft_speed_kmh = float(f_cfg['highway_soft_speed_kmh'])
        if 'hard_max_speed_kmh' in f_cfg: cfg.hard_max_speed_kmh = float(f_cfg['hard_max_speed_kmh'])
        if 'dwell_speed_threshold_kmh' in f_cfg: cfg.dwell_speed_threshold_kmh = float(f_cfg['dwell_speed_threshold_kmh'])

        tr = raw.get('trajectory', {})
        if 'min_match_score' in tr: cfg.min_match_score = float(tr['min_match_score'])
        if 'investigation_mode' in tr: cfg.investigation_mode = bool(tr['investigation_mode'])
        if 'max_candidate_sightings' in tr: cfg.max_candidate_sightings = int(tr['max_candidate_sightings'])
        if 'max_alternative_paths' in tr: cfg.max_alternative_paths = int(tr['max_alternative_paths'])
        if 'ambiguity_margin' in tr: cfg.ambiguity_margin = float(tr['ambiguity_margin'])
        if 'collapse_same_camera_dwell' in tr: cfg.collapse_same_camera_dwell = bool(tr['collapse_same_camera_dwell'])

        sp = raw.get('spatial', {})
        if 'default_nearby_radius_m' in sp: cfg.default_nearby_radius_m = float(sp['default_nearby_radius_m'])
        if 'max_nearby_radius_m' in sp: cfg.max_nearby_radius_m = float(sp['max_nearby_radius_m'])

        cw = raw.get('confidence', {})
        if 'identity_weight' in cw: cfg.identity_weight = float(cw['identity_weight'])
        if 'timing_weight' in cw: cfg.timing_weight = float(cw['timing_weight'])
        if 'spatial_weight' in cw: cfg.spatial_weight = float(cw['spatial_weight'])
        if 'feasibility_weight' in cw: cfg.feasibility_weight = float(cw['feasibility_weight'])
        if 'dominance_weight' in cw: cfg.dominance_weight = float(cw['dominance_weight'])

        gj = raw.get('geojson', {})
        if 'decimal_precision' in gj: cfg.decimal_precision = int(gj['decimal_precision'])

        return cfg
