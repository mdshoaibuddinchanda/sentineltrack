from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Callable, Dict, Optional
from pydantic import ValidationError

try:
    from ..errors import InvalidQueryParameterError, VMSConnectorAPIError
    from ..schemas.cameras import (
        CameraBulkImportRequest,
        CameraBulkImportResponse,
        CameraRegistryInput,
        VMSConnectorListResponse,
        VMSConnectorStatus,
        VMSConnectorSyncRequest,
    )
    from .camera_service import CameraService
except (ImportError, ValueError):
    err_m = importlib.import_module("08_backend.errors")
    InvalidQueryParameterError = err_m.InvalidQueryParameterError
    VMSConnectorAPIError = err_m.VMSConnectorAPIError
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraBulkImportRequest = cam_m.CameraBulkImportRequest
    CameraBulkImportResponse = cam_m.CameraBulkImportResponse
    CameraRegistryInput = cam_m.CameraRegistryInput
    VMSConnectorListResponse = cam_m.VMSConnectorListResponse
    VMSConnectorStatus = cam_m.VMSConnectorStatus
    VMSConnectorSyncRequest = cam_m.VMSConnectorSyncRequest
    CameraService = importlib.import_module("08_backend.services.camera_service").CameraService


def _vms_module():
    return importlib.import_module("00_foundation.vms")


class VMSIntegrationService:
    """Load trusted connector definitions and route normalized records through audited onboarding."""

    def __init__(self, camera_service: Optional[CameraService] = None, config_path: Optional[str] = None):
        self.camera_service = camera_service or CameraService()
        self.config_path = Path(
            config_path
            or os.getenv("SENTINEL_VMS_CONNECTOR_CONFIG", "configs/vms_connectors.json")
        )

    def _definitions(self):
        return _vms_module().load_connector_definitions(self.config_path)

    @staticmethod
    def _missing_env(definition) -> list[str]:
        names = [
            definition.username_env,
            definition.password_env,
            definition.bearer_token_env,
        ]
        return [name for name in names if name and not os.getenv(name)]

    def list_connectors(self) -> VMSConnectorListResponse:
        definitions = self._definitions()
        items = []
        for definition in definitions:
            summary = definition.safe_summary()
            missing = self._missing_env(definition)
            if not definition.enabled:
                ready = False
                message = "Disabled until the department endpoint and credentials are approved."
            elif missing:
                ready = False
                message = "Required credential environment variables are not configured."
            else:
                ready = True
                message = "Configuration is ready for an operator-triggered validation."
            items.append(VMSConnectorStatus(
                **summary,
                ready=ready,
                readiness_message=message,
            ))
        return VMSConnectorListResponse(
            config_path=str(self.config_path),
            items=items,
            total=len(items),
        )

    def _get_enabled_definition(self, connector_id: str):
        definitions = {definition.connector_id: definition for definition in self._definitions()}
        definition = definitions.get(connector_id)
        if definition is None:
            raise InvalidQueryParameterError(f"VMS connector '{connector_id}' is not configured.")
        if not definition.enabled:
            raise InvalidQueryParameterError(
                f"VMS connector '{connector_id}' is disabled; approve its endpoint before use."
            )
        missing = self._missing_env(definition)
        if missing:
            raise InvalidQueryParameterError(
                "The connector is enabled but required credential environment variables are missing.",
                details={"missing_environment_variables": missing},
            )
        return definition

    @staticmethod
    def _registry_input(record) -> CameraRegistryInput:
        data = record.model_dump()
        return CameraRegistryInput(
            camera_id=data["camera_id"],
            name=data.get("name"),
            department=data.get("department"),
            organization=data.get("organization"),
            source_system=data.get("source_system") or "VMS",
            external_id=data.get("external_id") or data["camera_id"],
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            azimuth=data.get("azimuth"),
            location_quality=data.get("location_quality") or "UNKNOWN",
            coordinate_source=data.get("coordinate_source"),
            coordinate_accuracy_m=data.get("coordinate_accuracy_m"),
            coverage_radius_m=data.get("coverage_radius_m"),
            field_of_view_degrees=data.get("field_of_view_degrees"),
            rtsp_url=data.get("rtsp_url"),
            hls_url=data.get("hls_url"),
            webrtc_url=data.get("webrtc_url"),
            live=True if data.get("live") is None else bool(data.get("live")),
            metadata=data.get("raw_metadata") or {},
        )

    def sync(
        self,
        connector_id: str,
        request: VMSConnectorSyncRequest,
        before_commit: Optional[Callable[[Dict[str, object]], None]] = None,
    ) -> CameraBulkImportResponse:
        definition = self._get_enabled_definition(connector_id)
        vms = _vms_module()
        try:
            connector = vms.build_connector(definition)
            records = connector.discover()
            cameras = [self._registry_input(record) for record in records]
        except (vms.VMSConnectorError, ValidationError) as exc:
            raise VMSConnectorAPIError(
                str(exc) if isinstance(exc, vms.VMSConnectorError) else "A connector camera record failed registry validation.",
                details={
                    "connector_id": connector_id,
                    "connector_code": getattr(exc, "code", "INVALID_CONNECTOR_RECORD"),
                },
            ) from exc
        if not cameras:
            raise VMSConnectorAPIError(
                "The connector returned no camera records.",
                details={"connector_id": connector_id, "connector_code": "EMPTY_DISCOVERY"},
            )
        bulk_request = CameraBulkImportRequest(
            cameras=cameras,
            mode=request.mode,
            dry_run=request.dry_run,
        )
        return self.camera_service.bulk_import(
            bulk_request,
            before_commit=before_commit,
            onboarding_method=f"VMS_SYNC:{definition.connector_type.upper()}",
        )
