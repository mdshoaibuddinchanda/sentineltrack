from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .base import BaseVMSConnector, VMSConnectorError
from .ogc_features import OGCFeaturesConnector
from .onvif import ONVIFProfileTConnector


class ConnectorDefinition(BaseModel):
    """Non-secret connector definition. Credential values are resolved from env."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    connector_id: str = Field(..., min_length=1, max_length=128)
    connector_type: str
    enabled: bool = False
    organization: str = Field(..., min_length=1, max_length=256)
    source_system: str = Field(..., min_length=1, max_length=128)
    camera_id_prefix: str = Field(..., min_length=1, max_length=64)
    endpoint: str
    username_env: Optional[str] = None
    password_env: Optional[str] = None
    bearer_token_env: Optional[str] = None
    camera_external_id: Optional[str] = None
    allowed_service_hosts: list[str] = Field(default_factory=list, max_length=20)
    timeout_s: float = Field(default=15.0, ge=1.0, le=60.0)
    allow_insecure_http: bool = False
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    location_quality: str = "UNKNOWN"
    coordinate_source: Optional[str] = None

    @model_validator(mode="after")
    def validate_definition(self):
        connector_type = self.connector_type.strip().upper()
        if connector_type not in {"OGC_API_FEATURES", "ONVIF_PROFILE_T"}:
            raise ValueError("connector_type must be OGC_API_FEATURES or ONVIF_PROFILE_T")
        parsed = urlsplit(self.endpoint)
        allowed_schemes = {"https"} | ({"http"} if self.allow_insecure_http else set())
        if parsed.scheme.lower() not in allowed_schemes or not parsed.hostname:
            raise ValueError("endpoint must be HTTPS unless allow_insecure_http is explicitly enabled")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not contain embedded credentials")

        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_latitude != has_longitude:
            raise ValueError("latitude and longitude must be supplied together")
        quality = self.location_quality.strip().upper()
        if quality not in {"VERIFIED", "APPROXIMATE", "UNKNOWN"}:
            raise ValueError("location_quality must be VERIFIED, APPROXIMATE, or UNKNOWN")
        if not has_latitude and quality != "UNKNOWN":
            raise ValueError("location_quality must be UNKNOWN when coordinates are absent")
        if has_latitude and not self.coordinate_source:
            raise ValueError("coordinate_source is required whenever coordinates are supplied")

        if connector_type == "ONVIF_PROFILE_T":
            if not self.camera_external_id:
                raise ValueError("ONVIF_PROFILE_T requires camera_external_id")
            if bool(self.username_env) != bool(self.password_env):
                raise ValueError("ONVIF username_env and password_env must be configured together")
        self.connector_type = connector_type
        self.location_quality = quality
        return self

    def safe_summary(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "connector_type": self.connector_type,
            "enabled": self.enabled,
            "organization": self.organization,
            "source_system": self.source_system,
            "camera_id_prefix": self.camera_id_prefix,
            "endpoint_host": urlsplit(self.endpoint).hostname,
            "credential_env_configured": bool(self.username_env or self.password_env or self.bearer_token_env),
        }


def load_connector_definitions(path: str | Path) -> list[ConnectorDefinition]:
    config_path = Path(path)
    if not config_path.is_file():
        return []
    if config_path.stat().st_size > 1_000_000:
        raise VMSConnectorError("VMS connector configuration exceeds 1 MiB.", "CONFIG_TOO_LARGE")
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VMSConnectorError("VMS connector configuration is not valid JSON.", "INVALID_CONFIG") from exc
    connectors = payload.get("connectors") if isinstance(payload, dict) else None
    if not isinstance(connectors, list):
        raise VMSConnectorError("VMS connector configuration requires a connectors array.", "INVALID_CONFIG")
    try:
        definitions = [ConnectorDefinition.model_validate(item) for item in connectors]
    except ValidationError as exc:
        raise VMSConnectorError(
            "VMS connector configuration failed schema validation.",
            "INVALID_CONFIG",
        ) from exc
    ids = [definition.connector_id for definition in definitions]
    if len(ids) != len(set(ids)):
        raise VMSConnectorError("VMS connector_id values must be unique.", "DUPLICATE_CONNECTOR_ID")
    return definitions


def _env_secret(name: Optional[str], *, required: bool) -> Optional[str]:
    if not name:
        if required:
            raise VMSConnectorError("A required credential environment-variable name is missing.", "MISSING_CREDENTIAL")
        return None
    value = os.getenv(name)
    if required and not value:
        raise VMSConnectorError(
            f"Required connector credential environment variable '{name}' is not set.",
            "MISSING_CREDENTIAL",
        )
    return value


def build_connector(definition: ConnectorDefinition, *, session=None) -> BaseVMSConnector:
    connector_type = definition.connector_type.strip().upper()
    if connector_type == "OGC_API_FEATURES":
        return OGCFeaturesConnector(
            connector_id=definition.connector_id,
            organization=definition.organization,
            source_system=definition.source_system,
            items_url=definition.endpoint,
            camera_id_prefix=definition.camera_id_prefix,
            bearer_token=_env_secret(definition.bearer_token_env, required=False),
            timeout_s=definition.timeout_s,
            allow_insecure_http=definition.allow_insecure_http,
            session=session,
        )
    if connector_type == "ONVIF_PROFILE_T":
        if not definition.camera_external_id:
            raise VMSConnectorError("ONVIF connector requires camera_external_id.", "INVALID_CONFIG")
        username = _env_secret(definition.username_env, required=bool(definition.password_env))
        password = _env_secret(definition.password_env, required=bool(definition.username_env))
        return ONVIFProfileTConnector(
            connector_id=definition.connector_id,
            organization=definition.organization,
            source_system=definition.source_system,
            device_service_url=definition.endpoint,
            camera_external_id=definition.camera_external_id,
            camera_id_prefix=definition.camera_id_prefix,
            username=username,
            password=password,
            timeout_s=definition.timeout_s,
            allow_insecure_http=definition.allow_insecure_http,
            session=session,
            latitude=definition.latitude,
            longitude=definition.longitude,
            location_quality=definition.location_quality,
            coordinate_source=definition.coordinate_source,
            allowed_service_hosts=definition.allowed_service_hosts,
        )
    raise VMSConnectorError(
        f"Unsupported VMS connector type '{definition.connector_type}'.",
        "UNSUPPORTED_CONNECTOR",
    )
