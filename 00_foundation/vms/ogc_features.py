from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit

import requests

from ..catalogue.models import CameraRecord
from .base import BaseVMSConnector, VMSConnectorError, normalized_camera_id, validate_connector_url


MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_FEATURES = 5000


def _safe_stream_url(value: Any, schemes: set[str]) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in schemes or not parsed.hostname:
        raise VMSConnectorError("A VMS feature contains an invalid stream endpoint.", "INVALID_STREAM_URL")
    if parsed.username is not None or parsed.password is not None:
        raise VMSConnectorError(
            "A VMS feature returned credentials inside a stream URL; configure an external secret instead.",
            "CREDENTIALS_IN_URL",
        )
    return value.strip()


class OGCFeaturesConnector(BaseVMSConnector):
    """Read camera features from an OGC API Features collection."""

    connector_type = "OGC_API_FEATURES"

    def __init__(
        self,
        *,
        connector_id: str,
        organization: str,
        source_system: str,
        items_url: str,
        camera_id_prefix: str,
        bearer_token: Optional[str] = None,
        timeout_s: float = 15.0,
        allow_insecure_http: bool = False,
        session: Optional[requests.Session] = None,
    ):
        super().__init__(
            connector_id=connector_id,
            organization=organization,
            source_system=source_system,
        )
        self.items_url = validate_connector_url(
            items_url,
            allow_http=allow_insecure_http,
            label="OGC API Features items_url",
        )
        self.camera_id_prefix = camera_id_prefix
        self.bearer_token = bearer_token
        self.timeout_s = max(1.0, min(float(timeout_s), 60.0))
        self.session = session or requests.Session()

    def discover(self) -> list[CameraRecord]:
        headers = {
            "Accept": "application/geo+json, application/json",
            "User-Agent": "SentinelTrack/1.0 OGC-Features-Connector",
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        try:
            response = self.session.get(
                self.items_url,
                headers=headers,
                timeout=self.timeout_s,
                allow_redirects=False,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VMSConnectorError(
                f"OGC camera catalogue request failed: {type(exc).__name__}.",
                "OGC_CATALOGUE_UNREACHABLE",
            ) from exc

        content = response.content
        if len(content) > MAX_RESPONSE_BYTES:
            raise VMSConnectorError("OGC camera catalogue exceeds the 10 MiB safety limit.", "RESPONSE_TOO_LARGE")
        try:
            payload = response.json()
        except ValueError as exc:
            raise VMSConnectorError("OGC camera catalogue did not return valid JSON.", "INVALID_JSON") from exc
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise VMSConnectorError("OGC response must be a GeoJSON FeatureCollection.", "INVALID_FEATURE_COLLECTION")
        features = payload.get("features")
        if not isinstance(features, list):
            raise VMSConnectorError("OGC FeatureCollection has no features array.", "INVALID_FEATURE_COLLECTION")
        if len(features) > MAX_FEATURES:
            raise VMSConnectorError("OGC response exceeds the 5,000-feature batch limit.", "TOO_MANY_FEATURES")

        cameras: list[CameraRecord] = []
        for index, feature in enumerate(features, start=1):
            cameras.append(self._parse_feature(feature, index))
        return cameras

    def _parse_feature(self, feature: Any, index: int) -> CameraRecord:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise VMSConnectorError(f"OGC feature {index} is not a GeoJSON Feature.", "INVALID_FEATURE")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        external_id = feature.get("id") or properties.get("camera_id") or properties.get("id")
        if external_id is None:
            raise VMSConnectorError(f"OGC feature {index} has no camera identifier.", "INVALID_CAMERA_ID")
        external_id = str(external_id)

        latitude = longitude = None
        geometry = feature.get("geometry")
        if geometry is not None:
            if not isinstance(geometry, dict) or geometry.get("type") != "Point":
                raise VMSConnectorError(
                    f"OGC feature {index} must use Point geometry for a camera.",
                    "INVALID_CAMERA_GEOMETRY",
                )
            coordinates = geometry.get("coordinates")
            if (
                not isinstance(coordinates, list)
                or len(coordinates) < 2
                or not isinstance(coordinates[0], (int, float))
                or not isinstance(coordinates[1], (int, float))
                or not -180.0 <= float(coordinates[0]) <= 180.0
                or not -90.0 <= float(coordinates[1]) <= 90.0
            ):
                raise VMSConnectorError(f"OGC feature {index} has invalid WGS84 coordinates.", "INVALID_CAMERA_GEOMETRY")
            longitude, latitude = float(coordinates[0]), float(coordinates[1])

        streams = properties.get("streams") if isinstance(properties.get("streams"), dict) else {}
        location_quality = str(properties.get("location_quality") or "UNKNOWN").upper()
        if location_quality not in {"VERIFIED", "APPROXIMATE", "UNKNOWN"}:
            location_quality = "UNKNOWN"
        if latitude is None:
            location_quality = "UNKNOWN"

        raw_metadata = {
            "connector_provenance": {
                "connector_id": self.connector_id,
                "connector_type": self.connector_type,
                "source_items_host": urlsplit(self.items_url).hostname,
            },
            "source_properties": properties,
        }
        return CameraRecord(
            camera_id=normalized_camera_id(self.camera_id_prefix, external_id),
            external_id=external_id,
            name=properties.get("name") or properties.get("label"),
            department=properties.get("department"),
            organization=self.organization,
            source_system=self.source_system,
            onboarding_method="OGC_FEATURES_SYNC",
            latitude=latitude,
            longitude=longitude,
            azimuth=properties.get("azimuth"),
            location_quality=location_quality,
            coordinate_source=(
                str(properties.get("coordinate_source"))
                if properties.get("coordinate_source")
                else (f"OGC_API_FEATURES:{self.source_system}" if latitude is not None else None)
            ),
            coordinate_accuracy_m=properties.get("coordinate_accuracy_m"),
            coverage_radius_m=properties.get("coverage_radius_m"),
            field_of_view_degrees=properties.get("field_of_view_degrees"),
            rtsp_url=_safe_stream_url(properties.get("rtsp_url") or streams.get("rtsp"), {"rtsp", "rtsps"}),
            hls_url=_safe_stream_url(properties.get("hls_url") or streams.get("hls"), {"http", "https"}),
            webrtc_url=_safe_stream_url(
                properties.get("webrtc_url") or properties.get("whep_url") or streams.get("webrtc") or streams.get("whep"),
                {"http", "https"},
            ),
            live=True if properties.get("live") is None else properties.get("live"),
            raw_metadata=raw_metadata,
        )
