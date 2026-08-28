import pytest
import importlib
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app


class TestSecurityHeaders:
    def test_security_headers_present_on_responses(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

        # Check standard OWASP recommended security headers
        headers = resp.headers
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert "content-security-policy" in headers
        assert "referrer-policy" in headers

    def test_correlation_id_present(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        assert "x-response-time-ms" in resp.headers
