from typing import Dict, Any, List, Optional
from datetime import datetime
from .models import (
    RouteSighting,
    RouteSegment,
    TargetTrajectory,
    TrajectoryStatus
)


def export_trajectory_to_geojson(
    target_id: str,
    registration: str,
    sightings: List[RouteSighting],
    segments: List[RouteSegment],
    confidence: float,
    status: TrajectoryStatus,
    precision: int = 6,
    redact_plate: bool = False
) -> Dict[str, Any]:
    """
    Exports a target vehicle trajectory to an RFC-7946 compliant GeoJSON FeatureCollection.
    Coordinates are formatted as [longitude, latitude].
    """
    features: List[Dict[str, Any]] = []
    line_coordinates: List[List[float]] = []

    display_reg = (registration[:4] + '****' + registration[-2:]) if (redact_plate and len(registration) >= 8) else registration

    # 1. Point Features for Sightings
    for idx, s in enumerate(sightings):
        if s.latitude is not None and s.longitude is not None:
            lon = round(float(s.longitude), precision)
            lat = round(float(s.latitude), precision)
            coord = [lon, lat]

            # Avoid adding duplicate consecutive points to line geometry
            if not line_coordinates or line_coordinates[-1] != coord:
                line_coordinates.append(coord)

            ev_time_str = s.event_time_utc.isoformat() if isinstance(s.event_time_utc, datetime) else str(s.event_time_utc)

            pt_feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': coord
                },
                'properties': {
                    'feature_type': 'sighting_node',
                    'sequence_index': idx + 1,
                    'sighting_id': s.sighting_id,
                    'camera_id': s.camera_id,
                    'location_label': s.location_label,
                    'target_registration': display_reg,
                    'event_time_utc': ev_time_str,
                    'match_score': round(s.match_score, 4),
                    'match_class': s.match_class,
                    'time_quality': str(s.time_quality.value if hasattr(s.time_quality, 'value') else s.time_quality),
                    'location_quality': str(s.location_quality.value if hasattr(s.location_quality, 'value') else s.location_quality),
                    'support_count': s.support_count
                }
            }
            features.append(pt_feature)

    # 2. LineString Feature for the Reconstructed Trajectory
    if len(line_coordinates) >= 2:
        total_dist_m = sum(seg.distance_lower_bound_m for seg in segments)
        start_t = sightings[0].event_time_utc.isoformat() if sightings else None
        end_t = sightings[-1].event_time_utc.isoformat() if sightings else None

        line_feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': line_coordinates
            },
            'properties': {
                'feature_type': 'trajectory_path',
                'target_id': target_id,
                'target_registration': display_reg,
                'status': str(status.value if hasattr(status, 'value') else status),
                'trajectory_confidence': round(confidence, 4),
                'sighting_count': len(sightings),
                'camera_count': len(set(s.camera_id for s in sightings)),
                'total_lower_bound_distance_m': round(total_dist_m, 2),
                'start_time_utc': start_t,
                'end_time_utc': end_t,
                'disclaimer': 'LineString connects camera observation locations in selected chronological sequence. It does not represent reconstructed road-level travel.'
            }
        }
        features.append(line_feature)

    return {
        'type': 'FeatureCollection',
        'metadata': {
            'target_id': target_id,
            'target_registration': display_reg,
            'status': str(status.value if hasattr(status, 'value') else status),
            'confidence': round(confidence, 4),
            'generated_at_utc': datetime.now().isoformat(),
            'rfc_compliance': 'RFC-7946',
            'coordinate_system': 'EPSG:4326 (WGS84)'
        },
        'features': features
    }
