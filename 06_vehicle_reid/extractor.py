"""One lightweight, non-plate appearance embedding extractor."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional, Sequence

import cv2
import numpy as np

from .config import ReIDConfig
from .models import VehicleAppearanceEmbedding


LOGGER = logging.getLogger(__name__)


class ReIDModelUnavailable(RuntimeError):
    """Raised when the optional appearance model cannot be loaded."""


def assess_crop_quality(crop: Optional[np.ndarray]) -> float:
    """Return a bounded sharpness/size quality score for crop selection."""

    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
        return 0.0
    if crop.ndim not in (2, 3) or crop.shape[0] < 2 or crop.shape[1] < 2:
        return 0.0
    gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # log compression keeps quality useful for both CCTV and unit-test crops.
    sharpness_score = float(np.clip(np.log1p(sharpness) / 8.0, 0.0, 1.0))
    size_score = float(np.clip(min(crop.shape[:2]) / 160.0, 0.0, 1.0))
    return round(0.75 * sharpness_score + 0.25 * size_score, 6)


def mask_plate_region(
    crop: np.ndarray,
    plate_bbox: Optional[Sequence[float]],
    padding_fraction: float = 0.15,
) -> tuple[np.ndarray, bool]:
    """Blur a plate rectangle in local vehicle-crop coordinates."""

    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
        return crop, False
    if plate_bbox is None or len(plate_bbox) != 4:
        return crop.copy(), False

    h, w = crop.shape[:2]
    x1, y1, x2, y2 = (float(value) for value in plate_bbox)
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    x1 = max(0, int(round(x1 - bw * padding_fraction)))
    y1 = max(0, int(round(y1 - bh * padding_fraction)))
    x2 = min(w, int(round(x2 + bw * padding_fraction)))
    y2 = min(h, int(round(y2 + bh * padding_fraction)))
    if x2 <= x1 or y2 <= y1:
        return crop.copy(), False

    masked = crop.copy()
    region = masked[y1:y2, x1:x2]
    kernel = max(3, int(round(min(region.shape[:2]) / 3.0)) | 1)
    masked[y1:y2, x1:x2] = cv2.GaussianBlur(region, (kernel, kernel), 0)
    return masked, True


class AppearanceEmbeddingExtractor:
    """Torchvision MobileNetV3-Small feature extractor.

    This is deliberately an ImageNet appearance-retrieval baseline, not a
    vehicle-domain ReID claim. The classifier head is removed and the 576
    dimensional pooled feature is L2 normalized.
    """

    architecture = "torchvision.mobilenet_v3_small"
    license = "BSD-3-Clause (torchvision code; ImageNet weights provenance is recorded separately)"

    def __init__(
        self,
        config: Optional[ReIDConfig] = None,
        *,
        model: Any = None,
        device: Optional[str] = None,
        eager: bool = False,
    ) -> None:
        self.config = config or ReIDConfig.from_yaml()
        self.device_name = self._resolve_device(device or self.config.device)
        self.device = None
        self.model = model
        self._checkpoint_path: Optional[Path] = None
        self._load_error: Optional[str] = None
        if model is not None:
            try:
                import torch

                self.device = torch.device(self.device_name)
                self.model.to(self.device).eval()
            except Exception as exc:  # pragma: no cover - injected test backends
                self._load_error = str(exc)
        elif eager:
            self.load()

    @staticmethod
    def _resolve_device(requested: str) -> str:
        if requested and requested != "auto":
            return requested
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    @property
    def is_available(self) -> bool:
        return self.model is not None and self._load_error is None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    @property
    def embedding_dimension(self) -> int:
        return self.config.embedding_dimension

    def load(self) -> "AppearanceEmbeddingExtractor":
        if self.model is not None and self._load_error is None:
            return self
        try:
            import torch
            from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

            weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
            checkpoint_path = Path(self.config.checkpoint_path) if self.config.checkpoint_path else None
            if checkpoint_path is not None and not checkpoint_path.is_absolute():
                checkpoint_path = Path(__file__).resolve().parent.parent / checkpoint_path

            if checkpoint_path is not None and checkpoint_path.exists():
                model = mobilenet_v3_small(weights=None)
                state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
                model.load_state_dict(state)
                self._checkpoint_path = checkpoint_path
                self._verify_checkpoint(checkpoint_path)
            else:
                if not self.config.allow_checkpoint_download:
                    raise FileNotFoundError(
                        "MobileNetV3-Small checkpoint is absent and checkpoint download is disabled"
                    )
                model = mobilenet_v3_small(weights=weights, progress=True)
                cache_dir = Path(torch.hub.get_dir()) / "checkpoints"
                filename = Path(weights.url).name
                cached = cache_dir / filename
                self._checkpoint_path = cached if cached.exists() else None
                if self._checkpoint_path is not None:
                    self._verify_checkpoint(self._checkpoint_path)

            model.classifier = torch.nn.Identity()
            self.model = model.to(self.device_name).eval()
            self.device = torch.device(self.device_name)
            self._load_error = None
            return self
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            raise ReIDModelUnavailable(self._load_error) from exc

    def _verify_checkpoint(self, path: Path) -> None:
        expected = (self.config.checkpoint_sha256 or "").strip().lower()
        if not expected:
            return
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"ReID checkpoint SHA-256 mismatch: expected {expected}, got {actual}")

    def checkpoint_provenance(self) -> dict[str, Any]:
        path = self._checkpoint_path
        checksum = None
        if path is not None and path.exists():
            checksum = sha256_file(path)
        return {
            "architecture": self.architecture,
            "model": self.config.model_name,
            "model_version": self.config.model_version,
            "checkpoint_url": self.config.checkpoint_url,
            "checkpoint_path": str(path) if path else None,
            "checkpoint_sha256": checksum or self.config.checkpoint_sha256 or None,
            "license": self.license,
            "input_resolution": [self.config.input_width, self.config.input_height],
            "embedding_dimension": self.config.embedding_dimension,
            "device": self.device_name,
            "plate_region_masked_for_reid": self.config.plate_region_masked_for_reid,
        }

    def _prepare_tensor(
        self,
        crop: np.ndarray,
        plate_bbox: Optional[Sequence[float]],
    ) -> tuple[Any, bool]:
        import torch

        working = crop
        masked = False
        if self.config.plate_region_masked_for_reid:
            working, masked = mask_plate_region(
                working,
                plate_bbox,
                self.config.plate_mask_padding_fraction,
            )
        if working.ndim == 2:
            working = cv2.cvtColor(working, cv2.COLOR_GRAY2BGR)
        if working.ndim != 3 or working.shape[2] != 3:
            raise ValueError("Vehicle crop must have one grayscale or three BGR channels")
        resized = cv2.resize(
            working,
            (self.config.input_width, self.config.input_height),
            interpolation=cv2.INTER_AREA,
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb.copy()).permute(2, 0, 1).float().div(255.0)
        mean = torch.tensor([0.485, 0.456, 0.406], dtype=tensor.dtype).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], dtype=tensor.dtype).view(3, 1, 1)
        return (tensor - mean) / std, masked

    def embed_batch(
        self,
        crops: Sequence[Optional[np.ndarray]],
        plate_bboxes: Optional[Sequence[Optional[Sequence[float]]]] = None,
    ) -> list[Optional[np.ndarray]]:
        """Embed valid crops while preserving input order; invalid crops yield None."""

        if not self.is_available:
            self.load()
        import torch

        bboxes = list(plate_bboxes or [None] * len(crops))
        if len(bboxes) != len(crops):
            raise ValueError("plate_bboxes must have the same length as crops")
        tensors: list[Any] = []
        positions: list[int] = []
        for position, (crop, bbox) in enumerate(zip(crops, bboxes)):
            if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
                continue
            if crop.ndim < 2 or crop.shape[0] < self.config.minimum_crop_height or crop.shape[1] < self.config.minimum_crop_width:
                continue
            try:
                tensor, _ = self._prepare_tensor(crop, bbox)
            except (TypeError, ValueError, cv2.error):
                continue
            tensors.append(tensor)
            positions.append(position)

        output: list[Optional[np.ndarray]] = [None] * len(crops)
        if not tensors:
            return output
        batch = torch.stack(tensors).to(self.device)
        with torch.inference_mode():
            raw = self.model(batch)
            if isinstance(raw, (tuple, list)):
                raw = raw[0]
            raw = raw.reshape(raw.shape[0], -1).float()
            raw = torch.nn.functional.normalize(raw, p=2, dim=1)
        if raw.shape[1] != self.config.embedding_dimension:
            raise ValueError(
                f"Unexpected ReID embedding dimension {raw.shape[1]}, expected {self.config.embedding_dimension}"
            )
        vectors = raw.detach().cpu().numpy().astype(np.float32)
        for position, vector in zip(positions, vectors):
            output[position] = vector
        return output

    def embed(
        self,
        crop: Optional[np.ndarray],
        plate_bbox: Optional[Sequence[float]] = None,
    ) -> Optional[np.ndarray]:
        return self.embed_batch([crop], [plate_bbox])[0]

    def extract(
        self,
        crop: Optional[np.ndarray],
        *,
        camera_id: str,
        stream_epoch: int,
        track_id: int,
        event_time_utc: Any = None,
        plate_bbox: Optional[Sequence[float]] = None,
        crop_quality: Optional[float] = None,
        source_frame_metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[VehicleAppearanceEmbedding]:
        vector = self.embed(crop, plate_bbox)
        if vector is None:
            return None
        _, masked = mask_plate_region(
            crop,
            plate_bbox,
            self.config.plate_mask_padding_fraction,
        ) if self.config.plate_region_masked_for_reid else (crop, False)
        return VehicleAppearanceEmbedding(
            camera_id=camera_id,
            stream_epoch=stream_epoch,
            track_id=track_id,
            event_time_utc=event_time_utc,
            embedding=vector,
            model=self.config.model_name,
            model_version=self.config.model_version,
            crop_quality=assess_crop_quality(crop) if crop_quality is None else crop_quality,
            source_frame_metadata=dict(source_frame_metadata or {}),
            plate_region_masked_for_reid=masked if plate_bbox is not None else self.config.plate_region_masked_for_reid,
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
