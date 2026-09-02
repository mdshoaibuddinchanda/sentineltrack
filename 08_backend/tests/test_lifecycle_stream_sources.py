import importlib
from types import SimpleNamespace


lifecycle = importlib.import_module("08_backend.lifecycle")
catalogue_client = importlib.import_module("00_foundation.catalogue.client")


def _official_camera():
    return {
        "camera_id": "cam01",
        "rtsp_url": "rtsp://103.250.160.189:8554/stream/cam01",
        "hls_url": "https://cctv.corp8.cloud/cam01/index.m3u8",
    }


def test_official_rtsp_uses_authenticated_hls_as_runtime_fallback():
    config = SimpleNamespace(prefer_hls_for_official_feeds=False)

    primary, fallback = lifecycle._camera_stream_urls(
        _official_camera(), config, hls_authorized=True
    )

    assert primary.startswith("rtsp://")
    assert fallback.startswith("https://")


def test_catalogue_outage_never_attempts_hls_without_session_cookie():
    config = SimpleNamespace(prefer_hls_for_official_feeds=True)

    primary, fallback = lifecycle._camera_stream_urls(
        _official_camera(), config, hls_authorized=False
    )

    assert primary.startswith("rtsp://")
    assert fallback == ""


def test_catalogue_refresh_retries_transient_failure(monkeypatch):
    attempts = []

    class FakeClient:
        effective_host = "https://cctv.corp8.cloud"

        def fetch(self):
            attempts.append(1)
            if len(attempts) < 3:
                raise catalogue_client.CatalogueConnectionError("temporary outage")
            return [{"id": "cam01", "name": "Camera 1"}]

        def diagnostics(self):
            return {"authenticated": True, "session_cookie_count": 1}

    class FakeDatabase:
        def __init__(self):
            self.records = []

        def upsert_camera(self, camera):
            self.records.append(camera)

    monkeypatch.setattr(catalogue_client, "SentinelCatalogueClient", FakeClient)
    monkeypatch.setenv("SENTINEL_CATALOGUE_FETCH_ATTEMPTS", "3")
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)
    database = FakeDatabase()

    client, diagnostics = lifecycle._refresh_catalogue(
        database,
        SimpleNamespace(refresh_catalogue_on_start=True),
    )

    assert client is not None
    assert len(attempts) == 3
    assert len(database.records) == 1
    assert diagnostics["code"] == "READY"
    assert diagnostics["catalogue_attempts"] == 3
