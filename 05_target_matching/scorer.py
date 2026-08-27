import numpy as np
import importlib
from typing import Optional

from .models import MatchCandidate, MatchClass
from .distance import (
    is_exact_match,
    standard_levenshtein,
    position_weighted_edit_distance,
    calculate_normalized_similarity
)

gram_mod = importlib.import_module('04_plate_ocr.grammar')
score_indian_grammar = gram_mod.score_indian_grammar
generate_grammar_alternatives = gram_mod.generate_grammar_alternatives


class TargetMatchScorer:
    """
    Multi-feature target matching and candidate classification engine.
    Transforms noisy OCR track evidence into explainable, calibrated match scores.
    """

    def __init__(
        self,
        similarity_weight: float = 0.55,
        ocr_confidence_weight: float = 0.15,
        support_weight: float = 0.15,
        grammar_weight: float = 0.10,
        quality_weight: float = 0.05,
        confusion_cost: float = 0.20,
        high_prob_threshold: float = 0.85,
        probable_threshold: float = 0.70,
        possible_threshold: float = 0.50,
        exact_fast_path: bool = True
    ):
        self.w_sim = similarity_weight
        self.w_ocr = ocr_confidence_weight
        self.w_supp = support_weight
        self.w_gram = grammar_weight
        self.w_qual = quality_weight
        self.confusion_cost = confusion_cost

        self.high_prob_threshold = high_prob_threshold
        self.probable_threshold = probable_threshold
        self.possible_threshold = possible_threshold
        self.exact_fast_path = exact_fast_path

    def score_match(
        self,
        target_id: str,
        target_registration: str,
        observed_registration: str,
        camera_id: str = 'default',
        stream_epoch: int = 1,
        track_id: int = 1,
        first_pts_ms: float = 0.0,
        last_pts_ms: float = 0.0,
        ocr_confidence: float = 0.80,
        crop_quality: float = 0.70,
        grammar_score: Optional[float] = None,
        multi_frame_support: int = 1,
        total_hypotheses: int = 1,
        alternatives: Optional[list[tuple[str, float]]] = None
    ) -> MatchCandidate:
        t_reg = target_registration.strip()
        o_reg = observed_registration.strip()
        alts = alternatives or []

        gram_sc = grammar_score if grammar_score is not None else score_indian_grammar(o_reg)

        # 1. Exact Match Fast Path
        if self.exact_fast_path and is_exact_match(t_reg, o_reg):
            supp_sc = min(1.0, max(multi_frame_support, 1) / 3.0)
            score = 1.0
            reasons = [
                'Exact match: 100% identical registration string',
                f'OCR confidence: {ocr_confidence:.2f}',
                f'Multi-frame support: {multi_frame_support}/{max(total_hypotheses, 1)} observations'
            ]
            return MatchCandidate(
                target_id=target_id,
                target_registration=t_reg,
                observed_registration=o_reg,
                camera_id=camera_id,
                stream_epoch=stream_epoch,
                track_id=track_id,
                first_pts_ms=first_pts_ms,
                last_pts_ms=last_pts_ms,
                raw_distance=0,
                normalized_distance=0.0,
                confusion_distance=0.0,
                ocr_confidence=ocr_confidence,
                crop_quality=crop_quality,
                grammar_score=gram_sc,
                multi_frame_support=multi_frame_support,
                exact_match=True,
                match_score=1.0,
                match_class=MatchClass.EXACT,
                reasons=reasons,
                alternatives=alts
            )

        # 2. Distance Calculations
        raw_dist = standard_levenshtein(t_reg, o_reg)
        conf_dist, dist_reasons = position_weighted_edit_distance(
            t_reg, o_reg, base_confusion_cost=self.confusion_cost
        )
        norm_sim = calculate_normalized_similarity(t_reg, o_reg, conf_dist)
        norm_dist = 1.0 - norm_sim

        # 3. Multi-Frame Support Factor
        # Saturates at 3+ corroborating observations
        supp_factor = min(1.0, max(multi_frame_support, 1) / 3.0)

        # 4. Multi-Feature Composite Scoring
        composite_score = (
            self.w_sim * norm_sim +
            self.w_ocr * ocr_confidence +
            self.w_supp * supp_factor +
            self.w_gram * gram_sc +
            self.w_qual * crop_quality
        )

        # Gating: Damping if raw similarity is below 0.60
        if norm_sim < 0.60:
            composite_score *= (norm_sim / 0.60)

        # Penalty for single isolated frame observation
        if multi_frame_support == 1:
            composite_score *= 0.90

        final_score = round(float(np.clip(composite_score, 0.0, 0.99)), 4)

        # 5. Match Classification
        if final_score >= self.high_prob_threshold and norm_sim >= 0.80 and multi_frame_support >= 2:
            match_cls = MatchClass.HIGH_PROBABILITY
        elif final_score >= self.probable_threshold and norm_sim >= 0.65:
            match_cls = MatchClass.PROBABLE
        elif final_score >= self.possible_threshold:
            match_cls = MatchClass.POSSIBLE
        else:
            match_cls = MatchClass.REJECTED

        # 6. Detailed Structured Reasons
        reasons = list(dist_reasons)
        reasons.append(f'OCR confidence: {ocr_confidence:.2f}')
        reasons.append(f'Multi-frame support: {multi_frame_support}/{max(total_hypotheses, 1)} observations')
        reasons.append(f'Indian registration grammar score: {gram_sc:.2f}')

        return MatchCandidate(
            target_id=target_id,
            target_registration=t_reg,
            observed_registration=o_reg,
            camera_id=camera_id,
            stream_epoch=stream_epoch,
            track_id=track_id,
            first_pts_ms=first_pts_ms,
            last_pts_ms=last_pts_ms,
            raw_distance=raw_dist,
            normalized_distance=norm_dist,
            confusion_distance=conf_dist,
            ocr_confidence=ocr_confidence,
            crop_quality=crop_quality,
            grammar_score=gram_sc,
            multi_frame_support=multi_frame_support,
            exact_match=False,
            match_score=final_score,
            match_class=match_cls,
            reasons=reasons,
            alternatives=alts
        )
