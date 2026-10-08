"""Pure temporal-consensus helpers for isolated P11.5 experiments.

The functions accept candidate dictionaries rather than model objects.  This
keeps the temporal policy testable and prevents model imports from leaking
into API-role modules.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable


PLATE_ALPHANUMERIC = re.compile(r"^[A-Z0-9]+$")


def normalize_plate(text: str) -> str:
    """Normalize a candidate plate for consensus, without guessing digits."""

    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def _candidate_text(candidate: dict[str, Any]) -> str:
    return normalize_plate(candidate.get("text", candidate.get("plate_text", "")))


def _candidate_weight(candidate: dict[str, Any]) -> float:
    confidence = float(candidate.get("confidence", candidate.get("ocr_confidence", 1.0)) or 0.0)
    quality = float(candidate.get("quality", candidate.get("quality_score", 1.0)) or 0.0)
    detector = float(candidate.get("detector_confidence", 1.0) or 0.0)
    return max(0.0, min(1.0, confidence)) * max(0.0, min(1.0, quality)) * max(0.0, min(1.0, detector))


def temporal_vote(
    observations: Iterable[dict[str, Any]],
    *,
    min_confidence: float = 0.0,
    min_quality: float = 0.0,
    min_support: int = 1,
) -> dict[str, Any]:
    """Return a weighted, auditable consensus over frame-level OCR outputs.

    The selected text is only a consensus result; this function does not
    assert that it is ground truth.  Callers should evaluate it against a
    locked labelled set before promotion.
    """

    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"weight": 0.0, "support": 0, "frames": []})
    considered = 0
    for candidate in observations:
        text = _candidate_text(candidate)
        confidence = float(candidate.get("confidence", candidate.get("ocr_confidence", 0.0)) or 0.0)
        quality = float(candidate.get("quality", candidate.get("quality_score", 0.0)) or 0.0)
        if not text or not PLATE_ALPHANUMERIC.fullmatch(text) or confidence < min_confidence or quality < min_quality:
            continue
        considered += 1
        group = groups[text]
        group["weight"] += _candidate_weight(candidate)
        group["support"] += 1
        if "frame_index" in candidate:
            group["frames"].append(candidate["frame_index"])

    eligible = [(text, data) for text, data in groups.items() if data["support"] >= min_support]
    if not eligible:
        return {
            "status": "NO_CONSENSUS",
            "selected_text": None,
            "considered": considered,
            "candidate_groups": 0,
            "support": 0,
            "weight": 0.0,
            "frames": [],
        }
    selected_text, selected = max(eligible, key=lambda item: (item[1]["weight"], item[1]["support"], item[0]))
    return {
        "status": "CONSENSUS",
        "selected_text": selected_text,
        "considered": considered,
        "candidate_groups": len(groups),
        "support": int(selected["support"]),
        "weight": round(float(selected["weight"]), 6),
        "frames": sorted(selected["frames"]),
    }


def best_observation(observations: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Select one observation by quality-adjusted confidence."""

    candidates = [item for item in observations if _candidate_text(item)]
    return max(candidates, key=_candidate_weight, default=None)
