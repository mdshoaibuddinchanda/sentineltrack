from __future__ import annotations

import importlib.util
import shutil
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = ROOT / "experiments" / "archive" / "p11_5" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workspace_tmp():
    path = ROOT / "reports" / "p11_5" / f"_test_tmp_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_yolo_parser_accepts_box_and_polygon(workspace_tmp: Path) -> None:
    audit = load_tool("audit_dataset")
    label = workspace_tmp / "sample.txt"
    label.write_text("0 0.5 0.5 0.4 0.2\n0 0.1 0.2 0.3 0.2 0.3 0.2 0.1 0.2\n", encoding="utf-8")
    parsed = audit.parse_yolo(label, 100, 50)
    assert len(parsed["boxes"]) == 2
    assert len(parsed["polygons"]) == 1
    assert parsed["flags"] == []


def test_voc_parser_and_bbox_validation(workspace_tmp: Path) -> None:
    audit = load_tool("audit_dataset")
    xml = workspace_tmp / "sample.xml"
    xml.write_text(
        "<annotation><object><name>GJ01AB1234</name><bndbox>"
        "<xmin>2</xmin><ymin>3</ymin><xmax>98</xmax><ymax>47</ymax>"
        "</bndbox></object></annotation>",
        encoding="utf-8",
    )
    parsed = audit.parse_voc(xml)
    assert parsed["names"] == ["GJ01AB1234"]
    assert audit.boxes_valid(parsed["boxes"], 100, 50)
    assert not audit.boxes_valid([[10, 10, 10, 20]], 100, 50)


def test_grouped_assignments_keep_connected_identity_and_sequence_together() -> None:
    build = load_tool("build_v2")
    records = [
        {"sample_id": "a", "sequence_id": "video1", "plate_identity": "GJ01AB1234", "sha256": "a"},
        {"sample_id": "b", "sequence_id": "video1", "plate_identity": "", "sha256": "b"},
        {"sample_id": "c", "sequence_id": "", "plate_identity": "GJ01AB1234", "sha256": "c"},
    ]
    assignments = build.grouped_assignments(records)
    assert assignments["a"][1] == assignments["b"][1] == assignments["c"][1]


def test_bbox_to_yolo_clips_only_to_image_bounds() -> None:
    build = load_tool("build_v2")
    values = build.bbox_to_yolo([-2, 5, 110, 45], 100, 50)
    assert values is not None
    assert values == [0.5, 0.5, 1.0, 0.8]
    assert build.bbox_to_yolo([30, 30, 20, 40], 100, 50) is None


def test_quality_and_temporal_helpers_are_bounded() -> None:
    import numpy as np

    quality = load_tool("quality")
    temporal = load_tool("temporal")
    crop = np.full((40, 160, 3), 128, dtype=np.uint8)
    result = quality.crop_quality(crop, detector_confidence=0.75)
    assert 0.0 <= result["score"] <= 1.0
    consensus = temporal.temporal_vote(
        [
            {"text": "GJ01AB1234", "confidence": 0.9, "quality": 0.8, "frame_index": 1},
            {"text": "GJ01AB1234", "confidence": 0.8, "quality": 0.9, "frame_index": 2},
            {"text": "bad-value!", "confidence": 1.0, "quality": 1.0, "frame_index": 3},
        ],
        min_support=2,
    )
    assert consensus["status"] == "CONSENSUS"
    assert consensus["selected_text"] == "GJ01AB1234"
    assert consensus["support"] == 2


def test_profile_resolver_selects_existing_baseline_without_loading_models() -> None:
    resolver = load_tool("profile_resolver")
    result = resolver.resolve_profile("baseline", {"gpu_count": 0, "vram_mb": 0, "cuda": False})
    assert result["selected"] == "baseline"
    assert result["profile"]["precision"] == "fp32"


def test_synthetic_generator_is_deterministic(workspace_tmp: Path) -> None:
    generator = load_tool("synthetic_plates")
    first = generator.generate_dataset(workspace_tmp / "one", count=4, seed=7)
    second = generator.generate_dataset(workspace_tmp / "two", count=4, seed=7)
    assert first["count"] == second["count"] == 4
    assert first["split_counts"] == second["split_counts"]
    import json

    first_manifest = json.loads((workspace_tmp / "one" / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((workspace_tmp / "two" / "manifest.json").read_text(encoding="utf-8"))
    first_manifest.pop("generated_at_utc")
    second_manifest.pop("generated_at_utc")
    assert first_manifest == second_manifest
