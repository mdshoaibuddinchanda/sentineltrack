"""Deterministic one-to-one matching for detector evaluation."""

from __future__ import annotations

from typing import Any


def box_iou(left: list[float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def greedy_one_to_one_matches(
    predictions: list[dict[str, Any]],
    ground_truths: list[list[float]],
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Match every prediction/GT at most once, preferring highest IoU.

    Ties are resolved by confidence and then source order, making aggregate
    detector counts reproducible across evaluator entry points.
    """
    candidates: list[tuple[float, float, int, int]] = []
    for prediction_index, prediction in enumerate(predictions):
        for ground_truth_index, ground_truth in enumerate(ground_truths):
            score = box_iou(prediction["box"], ground_truth)
            if score >= threshold:
                candidates.append((score, float(prediction.get("conf", 0.0)), prediction_index, ground_truth_index))
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
    used_predictions: set[int] = set()
    used_ground_truths: set[int] = set()
    matches: list[dict[str, Any]] = []
    for score, _, prediction_index, ground_truth_index in candidates:
        if prediction_index in used_predictions or ground_truth_index in used_ground_truths:
            continue
        used_predictions.add(prediction_index)
        used_ground_truths.add(ground_truth_index)
        matches.append({
            "prediction_index": prediction_index,
            "ground_truth_index": ground_truth_index,
            "iou": round(score, 6),
        })
    return sorted(matches, key=lambda item: item["ground_truth_index"])
