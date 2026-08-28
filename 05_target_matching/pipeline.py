import uuid
import numpy as np
from typing import Optional, Any
from datetime import datetime, timezone

from .models import (
    MatchCandidate,
    MatchClass,
    Sighting,
    TargetMatchRecord,
    Alert,
    WatchlistEntry
)
from .config import TargetMatchingConfig
from .watchlist import WatchlistManager
from .scorer import TargetMatchScorer
from .alerts import AlertManager
from .repository import BaseTargetMatchingRepository, get_repository
from .normalizer import normalize_plate_text


class TargetMatchingPipeline:
    """
    End-to-End Target Matching & Intelligence Pipeline.
    Consumes Priority 4 TrackOCRResult evidence, matches against active watchlists,
    persists sightings, records evaluated matches, and dispatches idempotent alerts.
    """

    def __init__(
        self,
        config: Optional[TargetMatchingConfig] = None,
        watchlist_manager: Optional[WatchlistManager] = None,
        scorer: Optional[TargetMatchScorer] = None,
        alert_manager: Optional[AlertManager] = None,
        repository: Optional[BaseTargetMatchingRepository] = None
    ):
        self.config = config or TargetMatchingConfig.from_yaml()
        self.repository = repository or get_repository(self.config)
        self.watchlist_manager = watchlist_manager or WatchlistManager(config=self.config, repository=self.repository)
        self.scorer = scorer or TargetMatchScorer(config=self.config)
        self.alert_manager = alert_manager or AlertManager(config=self.config)

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

        # 1. Derive real crop quality from P4 hypotheses if available
        if hasattr(track_result, 'hypotheses') and track_result.hypotheses:
            qualities = [h.crop_quality for h in track_result.hypotheses if hasattr(h, 'crop_quality')]
            crop_quality = float(np.mean(qualities)) if qualities else 0.70
        else:
            crop_quality = 0.70  # Explicit documented neutral fallback

        ev_time = getattr(track_result, 'event_time_utc', None)
        ev_source = getattr(track_result, 'event_time_source', None)
        ev_quality = getattr(track_result, 'event_time_quality', None)
        ingest_time = getattr(track_result, 'ingest_time_utc', None)

        # 2. Shortlist Watchlist Candidates using Multi-Index Fast Path
        candidates_to_eval = self.watchlist_manager.lookup_candidates(obs_reg)
        if not candidates_to_eval:
            # Persist raw sighting for un-watchlisted vehicle (searchable in history)
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
                    'status': track_result.status,
                    'crop_quality': crop_quality
                },
                event_time_utc=ev_time,
                event_time_source=ev_source,
                event_time_quality=ev_quality,
                ingest_time_utc=ingest_time
            )
            self.repository.save_sighting(sighting)
            return [], [], sighting

        # 3. Score Candidates (Evaluating best text and credible P4 alternatives)
        ranked_candidates: list[tuple[MatchCandidate, WatchlistEntry]] = []
        alts = getattr(track_result, 'alternatives', []) or []

        for w_entry in candidates_to_eval:
            # Score against best text
            best_cand = self.scorer.score_match(
                target_id=w_entry.watchlist_id,
                target_registration=w_entry.normalized_registration,
                observed_registration=obs_reg,
                camera_id=track_result.camera_id,
                stream_epoch=track_result.stream_epoch,
                track_id=track_result.track_id,
                first_pts_ms=track_result.first_pts_ms,
                last_pts_ms=track_result.last_pts_ms,
                ocr_confidence=track_result.confidence,
                crop_quality=crop_quality,
                multi_frame_support=track_result.support_count,
                total_hypotheses=track_result.total_hypotheses,
                alternatives=alts,
                matched_from='BEST_TEXT',
                alternative_rank=0,
                alternative_support_score=1.0
            )
            best_cand.event_time_utc = ev_time
            best_cand.event_time_source = ev_source
            best_cand.event_time_quality = ev_quality
            best_cand.ingest_time_utc = ingest_time

            top_cand_for_target = best_cand

            # Check if any P4 alternative yields a higher match score for this target
            for rank_idx, (alt_text, alt_gram_sc) in enumerate(alts, 1):
                norm_alt = normalize_plate_text(alt_text)
                if norm_alt and norm_alt != obs_reg:
                    alt_cand = self.scorer.score_match(
                        target_id=w_entry.watchlist_id,
                        target_registration=w_entry.normalized_registration,
                        observed_registration=norm_alt,
                        camera_id=track_result.camera_id,
                        stream_epoch=track_result.stream_epoch,
                        track_id=track_result.track_id,
                        first_pts_ms=track_result.first_pts_ms,
                        last_pts_ms=track_result.last_pts_ms,
                        ocr_confidence=track_result.confidence,
                        crop_quality=crop_quality,
                        multi_frame_support=track_result.support_count,
                        total_hypotheses=track_result.total_hypotheses,
                        alternatives=alts,
                        matched_from='ALTERNATIVE',
                        alternative_rank=rank_idx,
                        alternative_support_score=alt_gram_sc
                    )
                    alt_cand.event_time_utc = ev_time
                    alt_cand.event_time_source = ev_source
                    alt_cand.event_time_quality = ev_quality
                    alt_cand.ingest_time_utc = ingest_time
                    if alt_cand.match_score > top_cand_for_target.match_score:
                        top_cand_for_target = alt_cand

            ranked_candidates.append((top_cand_for_target, w_entry))

        # Rank candidates by match score descending
        ranked_candidates.sort(key=lambda x: x[0].match_score, reverse=True)

        top_cand, top_w_entry = ranked_candidates[0]
        sighting_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # 4. Persist Vehicle Sighting
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
            created_at=now,
            raw_evidence={
                'support_count': track_result.support_count,
                'total_hypotheses': track_result.total_hypotheses,
                'status': track_result.status,
                'top_target': top_w_entry.normalized_registration,
                'crop_quality': crop_quality,
                'reasons': top_cand.reasons
            },
            event_time_utc=ev_time,
            event_time_source=ev_source,
            event_time_quality=ev_quality,
            ingest_time_utc=ingest_time
        )
        self.repository.save_sighting(sighting)

        # 5. Persist Evaluated Matches in target_matches table
        for cand, w_entry in ranked_candidates:
            if cand.match_score >= 0.50:
                try:
                    self.repository.save_watchlist_entry(w_entry)
                except Exception:
                    pass
                match_rec = TargetMatchRecord(
                    match_id=str(uuid.uuid4()),
                    sighting_id=sighting_id,
                    watchlist_id=w_entry.watchlist_id,
                    match_score=cand.match_score,
                    match_class=cand.match_class,
                    raw_distance=cand.raw_distance,
                    confusion_distance=cand.confusion_distance,
                    matched_from=cand.matched_from,
                    alternative_rank=cand.alternative_rank,
                    explanation=cand.reasons,
                    created_at=now
                )
                self.repository.save_target_match(match_rec)

        # 6. Generate Idempotent Alerts
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
