import uuid
from typing import Optional, Any
from datetime import datetime, timezone

from .models import (
    MatchCandidate,
    MatchClass,
    Sighting,
    Alert,
    WatchlistEntry
)
from .watchlist import WatchlistManager
from .scorer import TargetMatchScorer
from .alerts import AlertManager
from .repository import TargetMatchingRepository
from .normalizer import normalize_plate_text


class TargetMatchingPipeline:
    """
    End-to-End Target Matching & Intelligence Pipeline.
    Consumes Priority 4 TrackOCRResult evidence, matches against active watchlists,
    persists sightings, and dispatches idempotent alerts.
    """

    def __init__(
        self,
        watchlist_manager: Optional[WatchlistManager] = None,
        scorer: Optional[TargetMatchScorer] = None,
        alert_manager: Optional[AlertManager] = None,
        repository: Optional[TargetMatchingRepository] = None
    ):
        self.watchlist_manager = watchlist_manager or WatchlistManager()
        self.scorer = scorer or TargetMatchScorer()
        self.alert_manager = alert_manager or AlertManager()
        self.repository = repository or TargetMatchingRepository()

    def process_track_ocr_result(
        self,
        track_result: Any  # TrackOCRResult from 04_plate_ocr
    ) -> tuple[list[MatchCandidate], list[Alert], Optional[Sighting]]:
        """
        Processes a multi-frame TrackOCRResult from Priority 4.
        Returns:
            tuple[ranked_candidates: list[MatchCandidate], generated_alerts: list[Alert], sighting: Optional[Sighting]]
        """
        if not track_result or not track_result.best_text:
            return [], [], None

        obs_reg = normalize_plate_text(track_result.best_text)
        if not obs_reg or len(obs_reg) < 4:
            return [], [], None

        # 1. Shortlist Watchlist Candidates using Multi-Index Fast Path
        candidates_to_eval = self.watchlist_manager.lookup_candidates(obs_reg)
        if not candidates_to_eval:
            # If no active watchlist matches, still persist sighting record if evidence is solid
            sighting_id = str(uuid.uuid4())
            sighting = Sighting(
                sighting_id=sighting_id,
                camera_id=track_result.camera_id,
                stream_epoch=track_result.stream_epoch,
                track_id=track_result.track_id,
                first_pts_ms=track_result.first_pts_ms,
                last_pts_ms=track_result.last_pts_ms,
                registration_candidate=obs_reg,
                confidence=track_result.confidence,
                match_score=0.0,
                match_class=MatchClass.REJECTED,
                raw_evidence={
                    'support_count': track_result.support_count,
                    'total_hypotheses': track_result.total_hypotheses,
                    'status': track_result.status
                }
            )
            self.repository.save_sighting(sighting)
            return [], [], sighting

        # 2. Score Candidates
        ranked_candidates: list[tuple[MatchCandidate, WatchlistEntry]] = []
        for w_entry in candidates_to_eval:
            candidate = self.scorer.score_match(
                target_id=w_entry.watchlist_id,
                target_registration=w_entry.normalized_registration,
                observed_registration=obs_reg,
                camera_id=track_result.camera_id,
                stream_epoch=track_result.stream_epoch,
                track_id=track_result.track_id,
                first_pts_ms=track_result.first_pts_ms,
                last_pts_ms=track_result.last_pts_ms,
                ocr_confidence=track_result.confidence,
                crop_quality=0.80,
                multi_frame_support=track_result.support_count,
                total_hypotheses=track_result.total_hypotheses,
                alternatives=track_result.alternatives
            )
            ranked_candidates.append((candidate, w_entry))

        # Rank by match score descending
        ranked_candidates.sort(key=lambda x: x[0].match_score, reverse=True)

        top_cand, top_w_entry = ranked_candidates[0]

        # 3. Persist Sighting
        sighting_id = str(uuid.uuid4())
        sighting = Sighting(
            sighting_id=sighting_id,
            camera_id=track_result.camera_id,
            stream_epoch=track_result.stream_epoch,
            track_id=track_result.track_id,
            first_pts_ms=track_result.first_pts_ms,
            last_pts_ms=track_result.last_pts_ms,
            registration_candidate=obs_reg,
            confidence=track_result.confidence,
            match_score=top_cand.match_score,
            match_class=top_cand.match_class,
            target_id=top_w_entry.watchlist_id,
            raw_evidence={
                'support_count': track_result.support_count,
                'total_hypotheses': track_result.total_hypotheses,
                'status': track_result.status,
                'top_target': top_w_entry.normalized_registration,
                'reasons': top_cand.reasons
            }
        )
        self.repository.save_sighting(sighting)

        # 4. Generate Idempotent Alerts
        generated_alerts = []
        for cand, w_entry in ranked_candidates:
            if cand.match_class in (MatchClass.EXACT, MatchClass.HIGH_PROBABILITY):
                alert, is_new, reason = self.alert_manager.process_match(
                    candidate=cand,
                    watchlist_entry=w_entry,
                    sighting_id=sighting_id
                )
                if alert:
                    if is_new:
                        self.repository.save_alert(alert)
                    generated_alerts.append(alert)

        return [c[0] for c in ranked_candidates], generated_alerts, sighting
