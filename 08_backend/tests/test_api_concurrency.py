import concurrent.futures
import pytest
import importlib
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app


def test_concurrent_api_health_requests():
    client = TestClient(app)

    def fetch_health():
        res = client.get("/health")
        return res.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_health) for _ in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(results)
    assert len(results) == 50


def test_concurrent_api_cameras_list():
    client = TestClient(app)

    def fetch_cameras():
        res = client.get("/api/v1/cameras?limit=10")
        return res.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_cameras) for _ in range(30)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(results)
    assert len(results) == 30
