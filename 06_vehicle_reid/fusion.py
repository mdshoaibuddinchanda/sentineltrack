"""Deterministic, conservative fusion with the existing P5 MatchCandidate."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Optional

from .config import ReIDConfig
from .models import AppearanceEvidence, ReIDCandidate, ReIDDecision


target_models = importlib.import_module("05_target_matching.models")
MatchCandidate = target_models.MatchCandidate
MatchClass = target_models.MatchClass


@dataclass
class ReIDFusionResult:
    """P6 output; P5 candidates remain the authoritative ANPR contract."""

    candidate: Optional[object]
    evidence_level: AppearanceEvidence
    decision: ReIDDecision
    identity_source: str
    reid_score: Optional[float]
    reid_can_override: bool
    automated_alert_allowed: bool
    match_class: str
    alert_severity: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_level": self.evidence_level.value,
            "decision": self.decision.value,
            "identity_source": self.identity_source,
            "reid_score": self.reid_score,
            "reid_can_override": self.reid_can_override,
            "automated_alert_allowed": self.automated_alert_allowed,
            "match_class": self.match_class,
            "alert_severity": self.alert_severity,
            "reasons": list(self.reasons),
        }


class ReIDFusion:
    """Applies only bounded supporting evidence and preserves P5 safeguards."""

    def __init__(self, config: Optional[ReIDConfig] = None) -> None:
        self.config = config or ReIDConfig.from_yaml()

    def infer_evidence_level(
        self,
        candidate: Optional[object],
        explicit: Optional[AppearanceEvidence] = None,
    ) -> AppearanceEvidence:
        if explicit is not None:
            return explicit
        if candidate is None:
            return AppearanceEvidence.NO_USABLE_PLATE
        observed = str(getattr(candidate, "observed_registration", "") or "").strip()
        if not observed:
            return AppearanceEvidence.NO_USABLE_PLATE
        match_class = getattr(candidate, "match_class", None)
        is_strong_class = match_class in (MatchClass.EXACT, MatchClass.HIGH_PROBABILITY)
        is_exact = bool(getattr(candidate, "exact_match", False)) or is_strong_class
        confidence = float(getattr(candidate, "ocr_confidence", 0.0) or 0.0)
        support = int(getattr(candidate, "multi_frame_support", 0) or 0)
        if is_exact and confidence >= 0.85 and support >= 2:
            return AppearanceEvidence.STRONG_PLATE
        return AppearanceEvidence.PARTIAL_PLATE

    def fuse(
        self,
        candidate: Optional[object],
        reid_candidate: Optional[ReIDCandidate] = None,
        *,
        evidence_level: Optional[AppearanceEvidence] = None,
    ) -> ReIDFusionResult:
        level = self.infer_evidence_level(candidate, evidence_level)
        score = None if reid_candidate is None else float(reid_candidate.reid_score)

        if level == AppearanceEvidence.STRONG_PLATE:
            reasons = ["ANPR_STRONG_REID_NOT_REQUIRED"]
            if reid_candidate is not None:
                if reid_candidate.decision == ReIDDecision.REJECTED:
                    reasons.append(reid_candidate.reason)
                elif reid_candidate.cosine_similarity < self.config.minimum_similarity_for_review:
                    reasons.append("ANPR_STRONG_REID_DISAGREEMENT_DIAGNOSTIC_ONLY")
                else:
                    reasons.append("ANPR_STRONG_REID_AGREEMENT_DIAGNOSTIC_ONLY")
                setattr(candidate, "reid_score", score)
            return ReIDFusionResult(
                candidate=candidate,
                evidence_level=level,
                decision=ReIDDecision.MATCH_SUPPORT,
                identity_source="ANPR",
                reid_score=score,
                reid_can_override=False,
                automated_alert_allowed=True,
                match_class=getattr(candidate, "match_class", MatchClass.REJECTED).value,
                alert_severity="ANPR_POLICY_CONTROLLED",
                reasons=reasons,
            )

        if level == AppearanceEvidence.PARTIAL_PLATE:
            if reid_candidate is None:
                return ReIDFusionResult(
                    candidate=candidate,
                    evidence_level=level,
                    decision=ReIDDecision.REVIEW,
                    identity_source="ANPR",
                    reid_score=None,
                    reid_can_override=False,
                    automated_alert_allowed=False,
                    match_class=getattr(candidate, "match_class", MatchClass.REJECTED).value,
                    alert_severity="REVIEW",
                    reasons=["PARTIAL_PLATE_REID_UNAVAILABLE"],
                )
            setattr(candidate, "reid_score", score)
            if reid_candidate.decision == ReIDDecision.REJECTED:
                return ReIDFusionResult(
                    candidate=candidate,
                    evidence_level=level,
                    decision=ReIDDecision.REJECTED,
                    identity_source="ANPR",
                    reid_score=score,
                    reid_can_override=False,
                    automated_alert_allowed=False,
                    match_class=getattr(candidate, "match_class", MatchClass.REJECTED).value,
                    alert_severity="REVIEW",
                    reasons=[reid_candidate.reason],
                )

            base_score = float(getattr(candidate, "match_score", 0.0) or 0.0)
            temporal = max(0.0, min(1.0, reid_candidate.temporal_compatibility))
            spatial = 1.0 if reid_candidate.spatial_route_feasibility is None else max(
                0.0, min(1.0, reid_candidate.spatial_route_feasibility)
            )
            combined = max(base_score, min(0.89, 0.65 * base_score + 0.25 * score + 0.10 * temporal * spatial))
            setattr(candidate, "match_score", round(combined, 4))
            current_class = getattr(candidate, "match_class", MatchClass.REJECTED)
            # Appearance may support a plausible partial plate, but cannot create EXACT.
            if current_class == MatchClass.REJECTED and combined >= 0.50:
                setattr(candidate, "match_class", MatchClass.POSSIBLE)
            elif current_class == MatchClass.POSSIBLE and combined >= 0.70:
                setattr(candidate, "match_class", MatchClass.PROBABLE)
            return ReIDFusionResult(
                candidate=candidate,
                evidence_level=level,
                decision=ReIDDecision.MATCH_SUPPORT if reid_candidate.decision == ReIDDecision.MATCH_SUPPORT else ReIDDecision.REVIEW,
                identity_source="ANPR_REID_SUPPORT",
                reid_score=score,
                reid_can_override=False,
                automated_alert_allowed=False,
                match_class=getattr(candidate, "match_class", MatchClass.REJECTED).value,
                alert_severity="REVIEW",
                reasons=["PARTIAL_PLATE_REID_SUPPORT", reid_candidate.reason],
            )

        # No usable plate: appearance is a review signal only.
        if reid_candidate is None:
            return ReIDFusionResult(
                candidate=None,
                evidence_level=level,
                decision=ReIDDecision.REVIEW,
                identity_source="REID_REVIEW",
                reid_score=None,
                reid_can_override=False,
                automated_alert_allowed=False,
                match_class=MatchClass.POSSIBLE.value,
                alert_severity="REVIEW",
                reasons=["APPEARANCE_ONLY_REVIEW_REQUIRED"],
            )
        if reid_candidate.decision == ReIDDecision.REJECTED:
            decision = ReIDDecision.REJECTED
            reasons = [reid_candidate.reason]
        else:
            decision = ReIDDecision.REVIEW
            reasons = ["APPEARANCE_ONLY_REVIEW_REQUIRED", reid_candidate.reason]
        return ReIDFusionResult(
            candidate=None,
            evidence_level=level,
            decision=decision,
            identity_source="REID_REVIEW",
            reid_score=score,
            reid_can_override=False,
            automated_alert_allowed=False,
            match_class=MatchClass.POSSIBLE.value if decision != ReIDDecision.REJECTED else MatchClass.REJECTED.value,
            alert_severity="REVIEW",
            reasons=reasons,
        )
