import math
from typing import Optional, Tuple, List
from .models import CameraGeo, LocationQuality

EARTH_RADIUS_METERS = 6371000.0


def validate_coordinates(latitude: Optional[float], longitude: Optional[float]) -> bool:
    """Validates that coordinates are finite numbers within physical WGS84 ranges."""
    if latitude is None or longitude is None:
        return False
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return False
    if math.isnan(latitude) or math.isnan(longitude) or math.isinf(latitude) or math.isinf(longitude):
        return False
    return -90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Computes great-circle distance between two WGS84 points in meters using Haversine formula.
    Returns 0.0 if coordinates are identical.
    """
    if not validate_coordinates(lat1, lon1) or not validate_coordinates(lat2, lon2):
        return 0.0

    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(EARTH_RADIUS_METERS * c, 2)


def calculate_segment_distance(
    cam1: Optional[CameraGeo],
    cam2: Optional[CameraGeo]
) -> Tuple[float, LocationQuality]:
    """
    Computes lower-bound distance between two cameras and determines composite location quality.
    """
    if not cam1 or not cam2:
        return 0.0, LocationQuality.UNKNOWN

    if not cam1.has_valid_coordinates or not cam2.has_valid_coordinates:
        return 0.0, LocationQuality.UNKNOWN

    dist = haversine_distance_m(cam1.latitude, cam1.longitude, cam2.latitude, cam2.longitude)

    if cam1.location_quality == LocationQuality.VERIFIED and cam2.location_quality == LocationQuality.VERIFIED:
        quality = LocationQuality.VERIFIED
    elif cam1.location_quality == LocationQuality.UNKNOWN or cam2.location_quality == LocationQuality.UNKNOWN:
        quality = LocationQuality.UNKNOWN
    else:
        quality = LocationQuality.APPROXIMATE

    return dist, quality
