import importlib
import pytest

spatial_mod = importlib.import_module('07_route_engine.spatial')
models_mod = importlib.import_module('07_route_engine.models')

validate_coordinates = spatial_mod.validate_coordinates
haversine_distance_m = spatial_mod.haversine_distance_m
calculate_segment_distance = spatial_mod.calculate_segment_distance
CameraGeo = models_mod.CameraGeo
LocationQuality = models_mod.LocationQuality


def test_validate_coordinates():
    assert validate_coordinates(23.0225, 72.5714) is True
    assert validate_coordinates(-90.0, 180.0) is True
    assert validate_coordinates(91.0, 0.0) is False
    assert validate_coordinates(0.0, 181.0) is False
    assert validate_coordinates(None, 72.0) is False
    assert validate_coordinates(float('nan'), 72.0) is False
    assert validate_coordinates(23.0, float('inf')) is False


def test_haversine_distance_known_points():
    # Ahmedabad (23.0225, 72.5714) to Gandhinagar (23.2156, 72.6369) ~22-23 km
    dist = haversine_distance_m(23.0225, 72.5714, 23.2156, 72.6369)
    assert 21000.0 < dist < 24000.0


def test_haversine_distance_zero_for_identical():
    dist = haversine_distance_m(23.0225, 72.5714, 23.0225, 72.5714)
    assert dist == 0.0


def test_calculate_segment_distance_quality():
    cam1 = CameraGeo('c1', latitude=23.0225, longitude=72.5714, location_quality=LocationQuality.VERIFIED)
    cam2 = CameraGeo('c2', latitude=23.0300, longitude=72.5800, location_quality=LocationQuality.VERIFIED)
    dist, qual = calculate_segment_distance(cam1, cam2)
    assert dist > 0.0
    assert qual == LocationQuality.VERIFIED

    # Approximate location
    cam3 = CameraGeo('c3', latitude=23.0400, longitude=72.5900, location_quality=LocationQuality.APPROXIMATE)
    dist2, qual2 = calculate_segment_distance(cam1, cam3)
    assert dist2 > 0.0
    assert qual2 == LocationQuality.APPROXIMATE

    # Missing location
    cam4 = CameraGeo('c4')
    dist3, qual3 = calculate_segment_distance(cam1, cam4)
    assert dist3 == 0.0
    assert qual3 == LocationQuality.UNKNOWN
