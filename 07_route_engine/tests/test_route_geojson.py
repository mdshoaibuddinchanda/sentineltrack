import json
import importlib
from datetime import datetime, timezone

gj_mod = importlib.import_module('07_route_engine.geojson')
models_mod = importlib.import_module('07_route_engine.models')

export_trajectory_to_geojson = gj_mod.export_trajectory_to_geojson
RouteSighting = models_mod.RouteSighting
RouteSegment = models_mod.RouteSegment
TrajectoryStatus = models_mod.TrajectoryStatus
FeasibilityClass = models_mod.FeasibilityClass


def test_export_geojson_structure():
    now = datetime.now(timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'c1', 1, 1, 0.0, 100.0, now, latitude=23.0225, longitude=72.5714)
    s2 = RouteSighting('s2', 'T1', 'GJ01AB1234', 'c2', 1, 1, 0.0, 100.0, now, latitude=23.0450, longitude=72.5800)

    seg = RouteSegment('s1', 's2', 'c1', 'c2', now, now, 2500.0, 120.0, 75.0, FeasibilityClass.FEASIBLE, 1.0)

    doc = export_trajectory_to_geojson('T1', 'GJ01AB1234', [s1, s2], [seg], 0.92, TrajectoryStatus.CONFIRMED_SEQUENCE)

    assert doc['type'] == 'FeatureCollection'
    assert doc['metadata']['rfc_compliance'] == 'RFC-7946'
    assert len(doc['features']) == 3  # 2 points + 1 LineString

    # Verify Point coordinates: [longitude, latitude]
    pt1 = doc['features'][0]
    assert pt1['geometry']['type'] == 'Point'
    assert pt1['geometry']['coordinates'] == [72.5714, 23.0225]

    # Verify LineString coordinates
    line = doc['features'][2]
    assert line['geometry']['type'] == 'LineString'
    assert line['geometry']['coordinates'] == [[72.5714, 23.0225], [72.5800, 23.0450]]
    assert 'disclaimer' in line['properties']

    # Verify JSON serializability
    json_str = json.dumps(doc)
    assert 'GJ01AB1234' in json_str


def test_export_geojson_redacted():
    now = datetime.now(timezone.utc)
    s1 = RouteSighting('s1', 'T1', 'GJ01AB1234', 'c1', 1, 1, 0.0, 100.0, now, latitude=23.0225, longitude=72.5714)
    doc = export_trajectory_to_geojson('T1', 'GJ01AB1234', [s1], [], 0.90, TrajectoryStatus.SINGLE_SIGHTING, redact_plate=True)

    json_str = json.dumps(doc)
    assert 'GJ01****34' in json_str
