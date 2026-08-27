from typing import Optional, Any
from datetime import datetime

from .normalizer import normalize_search_query
from .repository import BaseTargetMatchingRepository
from .scorer import TargetMatchScorer
from .models import MatchCandidate, MatchClass
from .config import TargetMatchingConfig


class HistoricalSearchService:
    """
    Search and rescoring service for historical vehicle sightings.
    Enables police operators to search past sightings across cameras, date ranges, and partial plate patterns.
    """

    def __init__(
        self,
        repository: BaseTargetMatchingRepository,
        scorer: Optional[TargetMatchScorer] = None,
        config: Optional[TargetMatchingConfig] = None
    ):
        self.repository = repository
        self.config = config or TargetMatchingConfig.from_yaml()
        self.scorer = scorer or TargetMatchScorer(config=self.config)

    def search_vehicle_history(
        self,
        query: str,
        camera_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        min_match_score: float = 0.0,
        max_results: int = 50
    ) -> list[dict[str, Any]]:
        norm_q, is_wildcard, is_valid = normalize_search_query(query)
        if not is_valid:
            return []

        pattern = norm_q if is_wildcard else f'{norm_q}'

        sightings = self.repository.query_sightings(
            registration_pattern=pattern,
            camera_id=camera_id,
            created_after=created_after,
            created_before=created_before,
            min_score=min_match_score,
            limit=max_results
        )

        return sightings

    def rescore_sighting(
        self,
        sighting_data: dict[str, Any],
        target_registration: str
    ) -> MatchCandidate:
        """
        Rescores a past sighting against a new or updated target using preserved raw evidence.
        """
        evidence = sighting_data.get('raw_evidence') or {}
        if isinstance(evidence, str):
            import json
            try:
                evidence = json.loads(evidence)
            except Exception:
                evidence = {}

        supp = sighting_data.get('support_count', evidence.get('support_count', 2))
        qual = sighting_data.get('crop_quality', evidence.get('crop_quality', 0.80))

        return self.scorer.score_match(
            target_id='rescore',
            target_registration=target_registration,
            observed_registration=sighting_data['registration_candidate'],
            camera_id=sighting_data.get('camera_id', 'unknown'),
            stream_epoch=sighting_data.get('stream_epoch', 1),
            track_id=sighting_data.get('track_id', 1),
            first_pts_ms=sighting_data.get('first_pts_ms', 0.0),
            last_pts_ms=sighting_data.get('last_pts_ms', 0.0),
            ocr_confidence=sighting_data.get('confidence', 0.80),
            crop_quality=qual,
            multi_frame_support=supp
        )
