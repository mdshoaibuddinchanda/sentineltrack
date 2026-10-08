import importlib
from pathlib import Path


launcher = importlib.import_module("main")


def test_launcher_frontend_uses_requested_api_and_websocket_ports(monkeypatch, tmp_path: Path):
    """A custom API port must reach both browser clients and WebSocket clients."""
    captured = {}

    class DummyProcess:
        def poll(self):
            return None

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return DummyProcess()

    monkeypatch.setattr(launcher, "LOG_DIR", tmp_path)
    monkeypatch.setattr(launcher, "ensure_frontend_dependencies", lambda: None)
    monkeypatch.setattr(launcher, "command", lambda name: "npm.cmd")
    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    try:
        launcher.start_frontend(ui_port=5174, api_port=8011)
        assert captured["args"][-2:] == ["--port", "5174"]
        assert captured["env"]["VITE_SENTINEL_API_URL"] == "http://127.0.0.1:8011"
        assert captured["env"]["VITE_SENTINEL_WS_URL"] == "ws://127.0.0.1:8011"
    finally:
        launcher.close_logs()


def test_launcher_rejects_a_used_port():
    """Port conflicts must fail before a stale backend can be mistaken for the new run."""
    import socket

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        try:
            launcher.assert_port_available("127.0.0.1", port, "API")
        except RuntimeError as exc:
            assert f"API port {port} is already in use" in str(exc)
        else:
            raise AssertionError("A used port was not rejected")


def test_backend_allowlist_follows_custom_ui_port(monkeypatch):
    """The configured API must allow the exact Vite origin selected by the launcher."""
    captured = {}

    class DummyUvicorn:
        @staticmethod
        def run(*args, **kwargs):
            captured["origins"] = launcher.os.environ["SENTINEL_ALLOWED_ORIGINS"]

    monkeypatch.setattr(launcher.importlib, "import_module", lambda name: type("App", (), {"app": object()}))
    monkeypatch.setitem(launcher.sys.modules, "uvicorn", DummyUvicorn)

    args = launcher.parse_args([
        "--backend-child",
        "--api-port",
        "8011",
        "--ui-port",
        "5174",
    ])
    launcher.run_backend_child(args)

    assert captured["origins"] == "http://localhost:5174,http://127.0.0.1:5174"
