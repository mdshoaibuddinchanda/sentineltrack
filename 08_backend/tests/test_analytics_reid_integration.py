"""Worker-level contract tests for the conditional P6 fallback gate."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
import importlib

import numpy as np

analytics_mod = importlib.import_module("08_backend.services.analytics_service")
p0_models = importlib.import_module("00_foundation.streams.models")
p5_models = importlib.import_module("05_target_matching.models")
reid_models = importlib.import_module("06_vehicle_reid.models")
reid_config = importlib.import_module("06_vehicle_reid.config")
reid_fusion = importlib.import_module("06_vehicle_reid.fusion")
reid_service = importlib.import_module("06_vehicle_reid.service")

AnalyticsWorker = analytics_mod.AnalyticsWorker
FramePacket = p0_models.FramePacket
AppearanceEvidence = reid_models.AppearanceEvidence
ReIDCandidate = reid_models.ReIDCandidate
ReIDDecision = reid_models.ReIDDecision
ReIDFusion = reid_fusion.ReIDFusion
ReIDConfig = reid_config.ReIDConfig
ReIDProcessResult = reid_service.ReIDProcessResult
TrackKey = reid_models.TrackKey
MatchCandidate = p5_models.MatchCandidate
MatchClass = p5_models.MatchClass


def _track(track_id: int = 7):
    return SimpleNamespace(
        camera_id="cam-new", stream_epoch=3, track_id=track_id, last_pts_ms=2500.0,
        class_name="car", confidence=0.95, x1=10.0, y1=20.0, x2=170.0, y2=120.0,
    )


def _packet():
    event_time = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    return FramePacket(
        camera_id="cam-new", pts_ms=2500.0,
        frame=np.full((180, 240, 3), 128, dtype=np.uint8), stream_epoch=3,
        event_time_utc=event_time, event_time_source="SOURCE_WALLCLOCK", event_time_quality="HIGH",
    )


def _p5_candidate(match_class=MatchClass.POSSIBLE, confidence=0.75, support=1):
    return MatchCandidate(
        target_id="target-1", target_registration="GJ01AB1234", observed_registration="GJ01AB1234",
        camera_id="cam-new", stream_epoch=3, track_id=7, first_pts_ms=2400.0, last_pts_ms=2500.0,
        raw_distance=0, normalized_distance=0.0, confusion_distance=0.0,
        ocr_confidence=confidence, crop_quality=0.9, grammar_score=1.0, multi_frame_support=support,
        exact_match=match_class == MatchClass.EXACT, match_score=0.84, match_class=match_class,
    )


class _RecordingReID:
    def __init__(self, candidate=None, profile=True):
        self.fusion = ReIDFusion(ReIDConfig())
        self.candidate = candidate
        self.profile = profile
        self.add_calls = []
        self.search_calls = 0

    def add_track_crop(self, track, crop, **kwargs):
        self.add_calls.append((track, crop, kwargs))
        key = TrackKey(str(track.camera_id), int(track.stream_epoch), int(track.track_id))
        return ReIDProcessResult(
            track_key=key,
            ran=kwargs.get("evidence_level") != AppearanceEvidence.STRONG_PLATE,
            stored=crop is not None,
            model_available=True,
            profile=object() if self.profile and crop is not None else None,
        )

    def search_track(self, key, **kwargs):
        self.search_calls += 1
        return [self.candidate] if self.candidate is not None else []

    def fuse_p5_candidate(self, candidate, reid_candidate=None, **kwargs):
        return self.fusion.fuse(candidate, reid_candidate, evidence_level=kwargs.get("evidence_level"))


def _reid_candidate(score=0.94):
    return ReIDCandidate(
        source_track=TrackKey("cam-new", 3, 7), candidate_track=TrackKey("cam-other", 2, 11),
        cosine_similarity=score, temporal_compatibility=1.0, spatial_route_feasibility=None,
        reid_score=score, decision=ReIDDecision.REVIEW, reason="REID_HIGH_SIMILARITY_REVIEW_ONLY",
    )


def test_strong_anpr_skips_reid_search_and_remains_authoritative():
    worker = AnalyticsWorker()
    service = _RecordingReID()
    worker._reid_service = service
    result = worker._process_reid_for_track(
        _packet(), _track(), [], SimpleNamespace(best_text="GJ01AB1234"),
        _p5_candidate(MatchClass.EXACT, confidence=0.99, support=2),
    )

    assert service.add_calls[0][1] is None
    assert service.add_calls[0][2]["evidence_level"] == AppearanceEvidence.STRONG_PLATE
    assert service.search_calls == 0
    assert result["identity_source"] == "ANPR"
    assert result["reid_can_override"] is False


def test_partial_plate_uses_reid_support_and_masks_local_plate_box():
    worker = AnalyticsWorker()
    service = _RecordingReID(_reid_candidate())
    worker._reid_service = service
    observation = SimpleNamespace(x1=30.0, y1=40.0, x2=70.0, y2=60.0, quality_score=0.9, track_id=7)
    cropper = importlib.import_module("03_plate_detection.cropper")

    with patch.object(cropper, "crop_vehicle", return_value=(np.ones((100, 160, 3), dtype=np.uint8), 10, 20, 170, 120)):
        result = worker._process_reid_for_track(
            _packet(), _track(), [observation], SimpleNamespace(best_text="GJ01AB12"), _p5_candidate()
        )

    assert service.add_calls[0][2]["evidence_level"] == AppearanceEvidence.PARTIAL_PLATE
    assert service.add_calls[0][2]["plate_bbox"] == (20.0, 20.0, 60.0, 40.0)
    assert service.add_calls[0][2]["source_frame_metadata"]["plate_region_masked_for_reid"] is True
    assert service.search_calls == 1
    assert result["identity_source"] == "ANPR_REID_SUPPORT"
    assert result["automated_alert_allowed"] is False
    assert result["reid_can_override"] is False


def test_no_plate_high_similarity_is_review_only():
    worker = AnalyticsWorker()
    service = _RecordingReID(_reid_candidate(0.98))
    worker._reid_service = service
    cropper = importlib.import_module("03_plate_detection.cropper")

    with patch.object(cropper, "crop_vehicle", return_value=(np.ones((100, 160, 3), dtype=np.uint8), 10, 20, 170, 120)):
        result = worker._process_reid_for_track(_packet(), _track(), [], None, None)

    assert result["evidence_level"] == AppearanceEvidence.NO_USABLE_PLATE.value
    assert result["identity_source"] == "REID_REVIEW"
    assert result["match_class"] == MatchClass.POSSIBLE.value
    assert result["alert_severity"] == "REVIEW"
    assert result["automated_alert_allowed"] is False


def test_reid_unavailable_leaves_p5_path_untouched():
    worker = AnalyticsWorker()
    worker._reid_service = None
    candidate = _p5_candidate()
    result = worker._process_reid_for_track(_packet(), _track(), [], None, candidate)

    assert result["identity_source"] == "REID_UNAVAILABLE"
    assert candidate.reid_score is None
    assert candidate.match_class == MatchClass.POSSIBLE
