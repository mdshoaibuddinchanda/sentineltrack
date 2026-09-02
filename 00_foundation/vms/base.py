from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import urlsplit

from ..catalogue.models import CameraRecord


class VMSConnectorError(RuntimeError):
    """A secret-free connector failure suitable for operator diagnostics."""

    def __init__(self, message: str, code: str = "VMS_CONNECTOR_ERROR"):
        super().__init__(message)
        self.code = code


def normalized_camera_id(prefix: str, external_id: str) -> str:
    clean_prefix = re.sub(r"[^A-Za-z0-9_.:-]+", "-", prefix.strip()).strip("-:")
    clean_external = re.sub(r"[^A-Za-z0-9_.:-]+", "-", external_id.strip()).strip("-:")
    if not clean_external:
        raise VMSConnectorError("A VMS camera record has no usable external identifier.", "INVALID_CAMERA_ID")
    value = f"{clean_prefix}:{clean_external}" if clean_prefix else clean_external
    if len(value) > 128:
        value = value[:128].rstrip("-:")
    return value


def validate_connector_url(url: str, *, allow_http: bool, label: str) -> str:
    parsed = urlsplit(url)
    allowed = {"https"} | ({"http"} if allow_http else set())
    if parsed.scheme.lower() not in allowed or not parsed.hostname:
        expected = "HTTPS (or explicitly enabled HTTP)" if allow_http else "HTTPS"
        raise VMSConnectorError(f"{label} must be a valid {expected} URL.", "INVALID_CONNECTOR_URL")
    if parsed.username is not None or parsed.password is not None:
        raise VMSConnectorError(f"{label} must not contain embedded credentials.", "CREDENTIALS_IN_URL")
    return url


class BaseVMSConnector(ABC):
    connector_type: str

    def __init__(self, *, connector_id: str, organization: str, source_system: str):
        self.connector_id = connector_id
        self.organization = organization
        self.source_system = source_system

    @abstractmethod
    def discover(self) -> list[CameraRecord]:
        """Return normalized camera records without persisting them."""

    def diagnostics(self) -> dict[str, object]:
        return {
            "connector_id": self.connector_id,
            "connector_type": self.connector_type,
            "organization": self.organization,
            "source_system": self.source_system,
        }
