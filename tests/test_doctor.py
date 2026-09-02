from __future__ import annotations

from types import SimpleNamespace

from tools import doctor


class _CatalogueError(RuntimeError):
    code = "CATALOGUE_UNREACHABLE"


def _install_catalogue_fakes(monkeypatch, fetch):
    client = SimpleNamespace(
        effective_host="https://cctv.example.test",
        fetch=fetch,
        diagnostics=lambda: {"session_cookie_count": 1},
    )
    client_module = SimpleNamespace(SentinelCatalogueClient=lambda timeout_s: client)
    parser_module = SimpleNamespace(parse_catalogue=lambda payload, base_host: payload["cameras"])

    def fake_import(name: str):
        if name == "00_foundation.catalogue.client":
            return client_module
        if name == "00_foundation.catalogue.parser":
            return parser_module
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import)
    monkeypatch.setattr(doctor.time, "sleep", lambda _seconds: None)


def test_catalogue_doctor_retries_a_transient_failure(monkeypatch):
    attempts = 0

    def fetch():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _CatalogueError("temporary timeout")
        return {"cameras": [{"id": "cam01"}]}

    _install_catalogue_fakes(monkeypatch, fetch)
    monkeypatch.setenv("SENTINEL_CATALOGUE_FETCH_ATTEMPTS", "3")

    result = doctor._catalogue_check()

    assert result.status == "PASS"
    assert "attempts=2" in result.details
    assert attempts == 2


def test_catalogue_doctor_caps_failed_retries(monkeypatch):
    attempts = 0

    def fetch():
        nonlocal attempts
        attempts += 1
        raise _CatalogueError("still unavailable")

    _install_catalogue_fakes(monkeypatch, fetch)
    monkeypatch.setenv("SENTINEL_CATALOGUE_FETCH_ATTEMPTS", "99")

    result = doctor._catalogue_check()

    assert result.status == "BLOCKED"
    assert "after 5 attempts" in result.details
    assert attempts == 5
