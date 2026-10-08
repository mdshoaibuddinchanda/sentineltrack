from __future__ import annotations

import copy
import importlib
from datetime import datetime, timedelta, timezone

import numpy as np
import torch


reid_config = importlib.import_module("06_vehicle_reid.config")
reid_extractor = importlib.import_module("06_vehicle_reid.extractor")
reid_fusion = importlib.import_module("06_vehicle_reid.fusion")
reid_gallery = importlib.import_module("06_vehicle_reid.gallery")
reid_matcher = importlib.import_module("06_vehicle_reid.matcher")
reid_models = importlib.import_module("06_vehicle_reid.models")
reid_service = importlib.import_module("06_vehicle_reid.service")
p5_models = importlib.import_module("05_target_matching.models")
tracking_models = importlib.import_module("02_tracking.models")

ReIDConfig = reid_config.ReIDConfig
AppearanceEmbeddingExtractor = reid_extractor.AppearanceEmbeddingExtractor
mask_plate_region = reid_extractor.mask_plate_region
ReIDFusion = reid_fusion.ReIDFusion
TrackEmbeddingGallery = reid_gallery.TrackEmbeddingGallery
ReIDMatcher = reid_matcher.ReIDMatcher
VehicleReIDService = reid_service.VehicleReIDService
AppearanceEvidence = reid_models.AppearanceEvidence
ReIDCandidate = reid_models.ReIDCandidate
ReIDDecision = reid_models.ReIDDecision
TrackKey = reid_models.TrackKey
VehicleAppearanceEmbedding = reid_models.VehicleAppearanceEmbedding
MatchCandidate = p5_models.MatchCandidate
MatchClass = p5_models.MatchClass
VehicleTrack = tracking_models.VehicleTrack


class FakeAppearanceModel(torch.nn.Module):
    def forward(self, batch):
        pooled = batch.mean(dim=(2, 3))
        return pooled.repeat(1, 192)


def p6_config(**overrides):
    values = {
        "device": "cpu",
        "allow_checkpoint_download": False,
        "gallery_ttl_seconds": 3600.0,
        "minimum_similarity_for_support": 0.90,
        "minimum_similarity_for_review": 0.80,
    }
    values.update(overrides)
    return ReIDConfig(**values)


def appearance(key, vector=None, event_time=None, quality=0.8, vehicle_class="car"):
    vector = np.asarray(vector if vector is not None else np.ones(576), dtype=np.float32)
    return VehicleAppearanceEmbedding(
        camera_id=key.camera_id,
        stream_epoch=key.stream_epoch,
        track_id=key.track_id,
        event_time_utc=event_time,
        embedding=vector,
        model="test-model",
        model_version="test",
        crop_quality=quality,
        source_frame_metadata={"vehicle_class": vehicle_class},
        plate_region_masked_for_reid=True,
    )


def reid_candidate(decision=ReIDDecision.MATCH_SUPPORT, similarity=0.96, temporal=1.0, spatial=None):
    return ReIDCandidate(
        source_track=TrackKey("query", 1, 1),
        candidate_track=TrackKey("cam-b", 1, 2),
        cosine_similarity=similarity,
        temporal_compatibility=temporal,
        spatial_route_feasibility=spatial,
        reid_score=similarity * temporal * (1.0 if spatial is None else spatial),
        decision=decision,
        reason="REID_HIGH_SIMILARITY" if decision == ReIDDecision.MATCH_SUPPORT else "REID_LOW_SIMILARITY",
    )


def p5_candidate(*, exact=False, match_class=MatchClass.PROBABLE, score=0.72, observed="GJ01AB123"):
    return MatchCandidate(
        target_id="watch-1",
        target_registration="GJ01AB1234",
        observed_registration=observed,
        camera_id="cam-a",
        stream_epoch=1,
        track_id=10,
        first_pts_ms=0.0,
        last_pts_ms=1000.0,
        raw_distance=1,
        normalized_distance=0.2,
        confusion_distance=0.2,
        ocr_confidence=0.90 if exact else 0.70,
        crop_quality=0.8,
        grammar_score=0.8,
        multi_frame_support=3 if exact else 1,
        exact_match=exact,
        match_score=1.0 if exact else score,
        match_class=MatchClass.EXACT if exact else match_class,
        reasons=["existing P5 evidence"],
    )


def test_plate_region_is_blurred_and_not_embedded_as_raw_pixels():
    crop = np.zeros((80, 160, 3), dtype=np.uint8)
    crop[30:50, 60:100] = (0, 0, 255)
    masked, was_masked = mask_plate_region(crop, (60, 30, 100, 50))
    assert was_masked is True
    assert masked.shape == crop.shape
    assert not np.array_equal(masked[30:50, 60:100], crop[30:50, 60:100])


def test_extractor_returns_l2_normalized_576d_embedding_and_handles_bad_crop():
    extractor = AppearanceEmbeddingExtractor(p6_config(), model=FakeAppearanceModel(), device="cpu")
    crop = np.full((96, 180, 3), 120, dtype=np.uint8)
    result = extractor.extract(crop, camera_id="cam-a", stream_epoch=1, track_id=3, plate_bbox=(60, 50, 100, 65))
    assert result is not None
    assert result.embedding.shape == (576,)
    assert np.isclose(np.linalg.norm(result.embedding), 1.0)
    assert result.plate_region_masked_for_reid is True
    assert extractor.extract(None, camera_id="cam-a", stream_epoch=1, track_id=3) is None
    assert extractor.extract(np.zeros((4, 4, 3), dtype=np.uint8), camera_id="cam-a", stream_epoch=1, track_id=3) is None


def test_gallery_caps_quality_crops_and_keeps_stream_epoch_in_key():
    gallery = TrackEmbeddingGallery(p6_config(), max_tracks=10, top_k_crops=5)
    key = TrackKey("cam-a", 4, 7)
    for index in range(7):
        gallery.add_observation(appearance(key, quality=index / 10.0), vehicle_class="car")
    profile = gallery.get(key)
    assert profile is not None
    assert len(profile.observations) == 5
    assert [item.crop_quality for item in profile.observations] == sorted([item.crop_quality for item in profile.observations], reverse=True)
    assert profile.embedding is not None
    assert np.isclose(np.linalg.norm(profile.embedding), 1.0)
    assert gallery.get(TrackKey("cam-a", 5, 7)) is None


def test_matcher_prunes_same_camera_epoch_and_applies_time_window():
    config = p6_config(search_time_window_seconds=60.0)
    gallery = TrackEmbeddingGallery(config)
    now = datetime.now(timezone.utc)
    gallery.add_observation(appearance(TrackKey("cam-a", 1, 2), event_time=now - timedelta(seconds=10)), vehicle_class="car")
    gallery.add_observation(appearance(TrackKey("cam-b", 1, 3), event_time=now - timedelta(seconds=10)), vehicle_class="car")
    gallery.add_observation(appearance(TrackKey("cam-c", 1, 4), event_time=now - timedelta(seconds=120)), vehicle_class="car")
    gallery.add_observation(appearance(TrackKey("cam-a", 2, 5), event_time=now - timedelta(seconds=10)), vehicle_class="car")
    query = appearance(TrackKey("cam-a", 1, 1), event_time=now)
    candidates = ReIDMatcher(config).search(query, gallery, vehicle_class="car", top_k=10)
    candidate_keys = {item.candidate_track for item in candidates}
    assert TrackKey("cam-b", 1, 3) in candidate_keys
    assert TrackKey("cam-a", 1, 2) not in candidate_keys
    assert TrackKey("cam-a", 2, 5) not in candidate_keys
    assert any(item.candidate_track == TrackKey("cam-c", 1, 4) and item.reason == "TEMPORALLY_INFEASIBLE" for item in candidates)


def test_route_feasibility_zero_rejects_candidate():
    gallery = TrackEmbeddingGallery(p6_config())
    source = appearance(TrackKey("query", 1, 1))
    gallery.add_observation(appearance(TrackKey("cam-b", 1, 2)), vehicle_class="car")
    candidates = ReIDMatcher(p6_config()).search(source, gallery, vehicle_class="car", route_feasibility=lambda _source, _candidate: 0.0)
    assert candidates[0].decision == ReIDDecision.REJECTED
    assert candidates[0].reason == "ROUTE_INFEASIBLE"


def test_review_only_mode_keeps_high_similarity_out_of_automatic_match_support():
    config = p6_config(review_only=True, minimum_similarity_for_support=0.90)
    gallery = TrackEmbeddingGallery(config)
    source = appearance(TrackKey("query", 1, 1))
    gallery.add_observation(appearance(TrackKey("cam-b", 1, 2)), vehicle_class="car")
    candidates = ReIDMatcher(config).search(source, gallery, vehicle_class="car")
    assert candidates[0].cosine_similarity > 0.99
    assert candidates[0].decision == ReIDDecision.REVIEW
    assert candidates[0].reason == "REID_HIGH_SIMILARITY_REVIEW_ONLY"


def test_strong_exact_plate_low_or_high_reid_always_remains_anpr():
    fusion = ReIDFusion(p6_config())
    for candidate in (reid_candidate(ReIDDecision.REJECTED, 0.20), reid_candidate(similarity=0.99)):
        p5 = p5_candidate(exact=True)
        before_class = p5.match_class
        result = fusion.fuse(p5, candidate, evidence_level=AppearanceEvidence.STRONG_PLATE)
        assert result.identity_source == "ANPR"
        assert result.reid_can_override is False
        assert p5.match_class == before_class == MatchClass.EXACT
        assert result.automated_alert_allowed is True


def test_high_probability_corroborated_plate_is_also_strong_anpr():
    p5 = p5_candidate(exact=False, match_class=MatchClass.HIGH_PROBABILITY, score=0.93)
    p5.multi_frame_support = 2
    p5.ocr_confidence = 0.90
    result = ReIDFusion(p6_config()).fuse(p5, reid_candidate(similarity=0.10))
    assert result.evidence_level == AppearanceEvidence.STRONG_PLATE
    assert result.identity_source == "ANPR"
    assert p5.match_class == MatchClass.HIGH_PROBABILITY


def test_partial_plausible_plate_is_strengthened_but_never_becomes_exact():
    p5 = p5_candidate(match_class=MatchClass.PROBABLE, score=0.70)
    result = ReIDFusion(p6_config()).fuse(p5, reid_candidate(similarity=0.97), evidence_level=AppearanceEvidence.PARTIAL_PLATE)
    assert result.identity_source == "ANPR_REID_SUPPORT"
    assert p5.reid_score is not None
    assert p5.match_score > 0.70
    assert p5.match_class != MatchClass.EXACT
    assert result.automated_alert_allowed is False


def test_conflicting_partial_plate_cannot_force_exact_and_no_plate_is_review_only():
    conflicting = p5_candidate(match_class=MatchClass.REJECTED, score=0.20, observed="ZZ99")
    conflicting.normalized_distance = 0.8
    conflict_result = ReIDFusion(p6_config()).fuse(conflicting, reid_candidate(similarity=0.99), evidence_level=AppearanceEvidence.PARTIAL_PLATE)
    assert conflicting.match_class != MatchClass.EXACT
    assert conflict_result.automated_alert_allowed is False
    no_plate = ReIDFusion(p6_config()).fuse(None, reid_candidate(similarity=0.99), evidence_level=AppearanceEvidence.NO_USABLE_PLATE)
    assert no_plate.decision == ReIDDecision.REVIEW
    assert no_plate.match_class == MatchClass.POSSIBLE.value
    assert no_plate.alert_severity == "REVIEW"
    assert no_plate.automated_alert_allowed is False
    assert "APPEARANCE_ONLY_REVIEW_REQUIRED" in no_plate.reasons


def test_p5_candidate_is_unchanged_when_reid_is_none():
    p5 = p5_candidate()
    before = copy.deepcopy(p5)
    result = ReIDFusion(p6_config()).fuse(p5, None)
    assert result.candidate is p5
    assert p5 == before
    assert p5.reid_score is None


def test_service_gate_skips_strong_plate_and_model_failure_is_graceful():
    config = p6_config()
    service = VehicleReIDService(config, extractor=AppearanceEmbeddingExtractor(config))
    track = VehicleTrack("cam-a", 1, 1, 0.0, 100.0, 2, "car", 0.9, 0.0, 0.0, 100.0, 100.0)
    skipped = service.add_track_crop(track, np.zeros((100, 100, 3), dtype=np.uint8), evidence_level=AppearanceEvidence.STRONG_PLATE)
    assert skipped.ran is False
    assert skipped.skip_reason == "ANPR_STRONG_REID_NOT_REQUIRED"
    failed = service.add_track_crop(track, np.zeros((100, 100, 3), dtype=np.uint8), evidence_level=AppearanceEvidence.NO_USABLE_PLATE)
    assert failed.ran is True
    assert failed.stored is False
    assert failed.model_available is False
    assert failed.error


def test_service_disabled_preserves_anpr_only_path():
    config = p6_config(enabled=False)
    extractor = AppearanceEmbeddingExtractor(config, model=FakeAppearanceModel(), device="cpu")
    service = VehicleReIDService(config, extractor=extractor)
    track = VehicleTrack("cam-a", 1, 1, 0.0, 100.0, 2, "car", 0.9, 0.0, 0.0, 100.0, 100.0)
    result = service.add_track_crop(track, np.zeros((100, 100, 3), dtype=np.uint8), evidence_level=AppearanceEvidence.NO_USABLE_PLATE)
    assert result.ran is False
    assert result.stored is False
    assert result.skip_reason == "REID_DISABLED"


def test_service_bad_crop_does_not_create_confident_result():
    config = p6_config()
    extractor = AppearanceEmbeddingExtractor(config, model=FakeAppearanceModel(), device="cpu")
    service = VehicleReIDService(config, extractor=extractor)
    track = VehicleTrack("cam-a", 1, 1, 0.0, 100.0, 2, "car", 0.9, 0.0, 0.0, 100.0, 100.0)
    result = service.add_track_crop(track, np.zeros((8, 8, 3), dtype=np.uint8), evidence_level=AppearanceEvidence.NO_USABLE_PLATE)
    assert result.stored is False
    assert result.skip_reason == "INVALID_OR_TINY_CROP"
