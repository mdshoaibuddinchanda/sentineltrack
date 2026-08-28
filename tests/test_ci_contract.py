import os
import sys
import subprocess
import pytest
import importlib

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_lightweight_api_import_isolation():
    """
    CI Contract 1: In API role, importing 08_backend.app must succeed in a clean process
    WITHOUT loading heavy/optional OCR or ML dependencies (PIL, easyocr, transformers).
    """
    code = """
import sys, os
os.environ['SENTINEL_PROCESS_ROLE'] = 'api'
os.environ['SENTINEL_REQUIRE_GPU'] = 'false'
os.environ['SENTINEL_PG_EVENT_BRIDGE'] = 'false'

import importlib
app_m = importlib.import_module('08_backend.app')
assert app_m.app is not None

# Verify optional ML packages are NOT eagerly loaded
for pkg in ['PIL', 'easyocr', 'transformers']:
    assert pkg not in sys.modules, f'Package {pkg} was eagerly imported into API process!'

print('API_IMPORT_ISOLATION_PASS')
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert res.returncode == 0, f"Subprocess failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "API_IMPORT_ISOLATION_PASS" in res.stdout


def test_target_normalizer_import_isolation():
    """
    CI Contract 2: Importing target normalizer and watchlist must succeed
    WITHOUT loading OCR recognizer engines.
    """
    code = """
import sys, os
import importlib

norm_m = importlib.import_module('05_target_matching.normalizer')
norm, valid, _ = norm_m.normalize_target_registration('MH 12 DE 1433')
assert valid is True
assert norm == 'MH12DE1433'

for pkg in ['PIL', 'easyocr', 'transformers']:
    assert pkg not in sys.modules, f'Package {pkg} leaked during normalizer import!'

print('NORMALIZER_IMPORT_ISOLATION_PASS')
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert res.returncode == 0, f"Subprocess failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "NORMALIZER_IMPORT_ISOLATION_PASS" in res.stdout


def test_route_inventory_and_policy_exactness():
    """
    CI Contract 3 & 4: Route inventory extraction via OpenAPI is non-empty,
    contains all canonical routes, and matches ROUTE_POLICY with zero missing/stale entries.
    """
    matrix_m = importlib.import_module("10_security.tests.test_complete_route_auth_matrix")
    routes = matrix_m.get_actual_application_routes()

    assert len(routes) >= 30, f"Unexpectedly few routes discovered: {len(routes)}"
    assert ("POST", "/api/v1/auth/login") in routes
    assert ("GET", "/health") in routes
    assert ("GET", "/api/v1/cameras") in routes
    assert ("GET", "/metrics/prometheus") in routes

    policy_routes = set(matrix_m.ROUTE_POLICY.keys())
    assert routes == policy_routes, f"Mismatch: missing={routes - policy_routes}, stale={policy_routes - routes}"


def test_api_process_role_lifecycle_behavior():
    """
    CI Contract 5: Under SENTINEL_PROCESS_ROLE=api, lifespan startup must NOT start AnalyticsWorker.
    """
    os.environ["SENTINEL_PROCESS_ROLE"] = "api"
    scale_cfg_m = importlib.import_module("11_scale_deployment.config")
    importlib.reload(scale_cfg_m)
    cfg = scale_cfg_m.get_scale_config()
    assert cfg.is_analytics_enabled() is False
    assert cfg.is_api_enabled() is True
