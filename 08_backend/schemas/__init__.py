try:
    from .common import PaginationParams, ErrorDetail, ErrorResponse, Envelope
    from .cameras import CameraResponse, CameraListResponse, CameraHealthResponse, CameraNearbyQuery
    from .targets import TargetCreateRequest, TargetUpdateRequest, TargetResponse, TargetListResponse, TargetPriorityEnum
    from .sightings import SightingResponse, SightingListResponse, VehicleHistoryResponse
    from .alerts import AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse
    from .routes import RouteSegmentResponse, RouteSightingResponse, RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection
    from .health import HealthResponse, ReadinessResponse, MetricsResponse
except (ImportError, ValueError):
    import importlib
    common_m = importlib.import_module("08_backend.schemas.common")
    PaginationParams, ErrorDetail, ErrorResponse, Envelope = common_m.PaginationParams, common_m.ErrorDetail, common_m.ErrorResponse, common_m.Envelope
    cam_m = importlib.import_module("08_backend.schemas.cameras")
    CameraResponse, CameraListResponse, CameraHealthResponse, CameraNearbyQuery = cam_m.CameraResponse, cam_m.CameraListResponse, cam_m.CameraHealthResponse, cam_m.CameraNearbyQuery
    tgt_m = importlib.import_module("08_backend.schemas.targets")
    TargetCreateRequest, TargetUpdateRequest, TargetResponse, TargetListResponse, TargetPriorityEnum = tgt_m.TargetCreateRequest, tgt_m.TargetUpdateRequest, tgt_m.TargetResponse, tgt_m.TargetListResponse, tgt_m.TargetPriorityEnum
    sight_m = importlib.import_module("08_backend.schemas.sightings")
    SightingResponse, SightingListResponse, VehicleHistoryResponse = sight_m.SightingResponse, sight_m.SightingListResponse, sight_m.VehicleHistoryResponse
    alt_m = importlib.import_module("08_backend.schemas.alerts")
    AlertResponse, AlertListResponse, AlertAckRequest, AlertAckResponse = alt_m.AlertResponse, alt_m.AlertListResponse, alt_m.AlertAckRequest, alt_m.AlertAckResponse
    rt_m = importlib.import_module("08_backend.schemas.routes")
    RouteSegmentResponse, RouteSightingResponse, RouteResponse, RouteSummaryResponse, GeoJSONFeatureCollection = rt_m.RouteSegmentResponse, rt_m.RouteSightingResponse, rt_m.RouteResponse, rt_m.RouteSummaryResponse, rt_m.GeoJSONFeatureCollection
    hlth_m = importlib.import_module("08_backend.schemas.health")
    HealthResponse, ReadinessResponse, MetricsResponse = hlth_m.HealthResponse, hlth_m.ReadinessResponse, hlth_m.MetricsResponse

__all__ = [
    "PaginationParams", "ErrorDetail", "ErrorResponse", "Envelope",
    "CameraResponse", "CameraListResponse", "CameraHealthResponse", "CameraNearbyQuery",
    "TargetCreateRequest", "TargetUpdateRequest", "TargetResponse", "TargetListResponse", "TargetPriorityEnum",
    "SightingResponse", "SightingListResponse", "VehicleHistoryResponse",
    "AlertResponse", "AlertListResponse", "AlertAckRequest", "AlertAckResponse",
    "RouteSegmentResponse", "RouteSightingResponse", "RouteResponse", "RouteSummaryResponse", "GeoJSONFeatureCollection",
    "HealthResponse", "ReadinessResponse", "MetricsResponse"
]
