import uuid
import pytest
import importlib
from unittest.mock import patch
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app


def test_create_target_success_and_normalization():
    client = TestClient(app)
    reg_input = f"gj 01 ab {uuid.uuid4().hex[:4]}"
    payload = {
        "registration": reg_input,
        "priority": "HIGH",
        "notes": "Test target for burglary investigation",
        "metadata": {"case_id": "FIR-2026-901"}
    }

    response = client.post("/api/v1/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "target_id" in data
    assert data["priority"] == "HIGH"
    # Verify plate was properly normalized
    clean_expected = reg_input.upper().replace(" ", "")
    assert data["normalized_registration"] == clean_expected
    assert data["enabled"] is True


def test_create_target_duplicate_rejection():
    client = TestClient(app)
    reg = f"GJ01DUP{uuid.uuid4().hex[:4].upper()}"
    payload = {
        "registration": reg,
        "priority": "NORMAL"
    }

    # First creation -> 201
    res1 = client.post("/api/v1/targets", json=payload)
    assert res1.status_code == 201

    # Second creation with identical plate -> 409 Conflict
    res2 = client.post("/api/v1/targets", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"]["code"] == "DUPLICATE_TARGET"


def test_create_target_database_failure_returns_503_and_rolls_back_memory():
    client = TestClient(app)
    reg = f"GJ01ERR{uuid.uuid4().hex[:4].upper()}"
    p5_repo = importlib.import_module("05_target_matching.repository")
    shared_wm = importlib.import_module("08_backend.services.target_service").get_shared_watchlist_manager()

    with patch.object(p5_repo.PostgresTargetMatchingRepository, "save_watchlist_entry", side_effect=ConnectionError("DB connection lost")):
        res = client.post("/api/v1/targets", json={"registration": reg, "priority": "HIGH"})
        assert res.status_code == 503
        data = res.json()
        assert data["error"]["code"] == "DATABASE_UNAVAILABLE"

    # Verify target does NOT exist in in-memory watchlist manager after failure
    assert reg not in shared_wm._exact_index
    for e in shared_wm._entries.values():
        assert e.registration != reg


def test_list_targets_and_pagination():
    client = TestClient(app)
    response = client.get("/api/v1/targets?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_target_by_id():
    client = TestClient(app)
    reg = f"GJ01GET{uuid.uuid4().hex[:4].upper()}"
    res = client.post("/api/v1/targets", json={"registration": reg, "priority": "CRITICAL"})
    target_id = res.json()["target_id"]

    get_res = client.get(f"/api/v1/targets/{target_id}")
    assert get_res.status_code == 200
    assert get_res.json()["target_id"] == target_id
    assert get_res.json()["priority"] == "CRITICAL"


def test_get_target_not_found():
    client = TestClient(app)
    response = client.get("/api/v1/targets/NONEXISTENT_TARGET_UUID")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TARGET_NOT_FOUND"


def test_update_target_endpoint():
    client = TestClient(app)
    reg = f"GJ01UPD{uuid.uuid4().hex[:4].upper()}"
    res = client.post("/api/v1/targets", json={"registration": reg, "priority": "LOW"})
    target_id = res.json()["target_id"]

    patch_res = client.patch(f"/api/v1/targets/{target_id}", json={"priority": "CRITICAL", "notes": "Upgraded urgency"})
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["priority"] == "CRITICAL"
    assert data["notes"] == "Upgraded urgency"


def test_update_target_database_failure_returns_503_and_rolls_back_memory():
    client = TestClient(app)
    reg = f"GJ01UPERR{uuid.uuid4().hex[:4].upper()}"
    res = client.post("/api/v1/targets", json={"registration": reg, "priority": "LOW", "notes": "Original notes"})
    target_id = res.json()["target_id"]

    shared_wm = importlib.import_module("08_backend.services.target_service").get_shared_watchlist_manager()
    p5_repo = importlib.import_module("05_target_matching.repository")

    with patch.object(p5_repo.PostgresTargetMatchingRepository, "save_watchlist_entry", side_effect=ConnectionError("DB connection lost")):
        patch_res = client.patch(f"/api/v1/targets/{target_id}", json={"priority": "CRITICAL", "notes": "Failed update notes"})
        assert patch_res.status_code == 503
        assert patch_res.json()["error"]["code"] == "DATABASE_UNAVAILABLE"

    # Verify in-memory entry retains original values after DB failure
    mem_entry = shared_wm.get_entry(target_id)
    assert mem_entry is not None
    assert mem_entry.priority.value == "LOW"
    assert mem_entry.notes == "Original notes"


def test_disable_target_endpoint():
    client = TestClient(app)
    reg = f"GJ01DIS{uuid.uuid4().hex[:4].upper()}"
    res = client.post("/api/v1/targets", json={"registration": reg})
    target_id = res.json()["target_id"]

    del_res = client.delete(f"/api/v1/targets/{target_id}")
    assert del_res.status_code == 200
    assert del_res.json()["enabled"] is False


def test_disable_target_database_failure_returns_503_and_rolls_back_memory():
    client = TestClient(app)
    reg = f"GJ01DISERR{uuid.uuid4().hex[:4].upper()}"
    res = client.post("/api/v1/targets", json={"registration": reg})
    target_id = res.json()["target_id"]

    shared_wm = importlib.import_module("08_backend.services.target_service").get_shared_watchlist_manager()
    p5_repo = importlib.import_module("05_target_matching.repository")

    with patch.object(p5_repo.PostgresTargetMatchingRepository, "save_watchlist_entry", side_effect=ConnectionError("DB connection lost")):
        del_res = client.delete(f"/api/v1/targets/{target_id}")
        assert del_res.status_code == 503
        assert del_res.json()["error"]["code"] == "DATABASE_UNAVAILABLE"

    # Verify target remains enabled in in-memory manager after DB failure
    mem_entry = shared_wm.get_entry(target_id)
    assert mem_entry is not None
    assert mem_entry.enabled is True
