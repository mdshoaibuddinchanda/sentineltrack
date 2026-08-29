import sys
import time
import json
import math
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Any
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib
backend_app = importlib.import_module("08_backend.app")
app = backend_app.app
sec_repo = importlib.import_module("10_security.repository")
sec_sess = importlib.import_module("10_security.sessions")
sec_pw = importlib.import_module("10_security.password")
sec_models = importlib.import_module("10_security.models")


def run_api_load_benchmark(concurrencies: List[int] = [1, 5, 10, 25, 50], requests_per_client: int = 20, output_json: str = "reports/p11/runs/api_load_benchmark.json"):
    print("==================================================")
    print("      SENTINELTRACK API CONCURRENCY BENCHMARK     ")
    print("==================================================")

    # Initialize in-memory security repository and admin/operator users
    test_repo = sec_repo.SqliteSecurityRepository(":memory:")
    test_session_mgr = sec_sess.SessionManager(repository=test_repo)
    sec_repo.set_security_repository(test_repo)
    sec_sess.set_session_manager(test_session_mgr)

    # Seed Admin User
    admin = sec_models.User(
        user_id="admin-1",
        username="admin",
        display_name="Administrator",
        password_hash=sec_pw.hash_password("SuperSecretAdminPass123!"),
        role=sec_models.UserRole.ADMIN,
        enabled=True
    )
    test_repo.save_user(admin)

    # Seed Operator User
    operator = sec_models.User(
        user_id="op-1",
        username="operator",
        display_name="Operator",
        password_hash=sec_pw.hash_password("OperatorPass12345!"),
        role=sec_models.UserRole.OPERATOR,
        enabled=True
    )
    test_repo.save_user(operator)

    client = TestClient(app)
    # Login to obtain session cookie
    login_resp = client.post("/api/v1/auth/login", json={"username": "operator", "password": "OperatorPass12345!"})
    cookie_val = login_resp.cookies.get("sentinel_session")

    endpoints = [
        "/health",
        "/api/v1/cameras",
        "/api/v1/targets",
        "/api/v1/alerts",
        "/api/v1/sightings"
    ]

    benchmark_results = {"concurrency_levels": {}}

    for conc in concurrencies:
        print(f"\n--- Testing Concurrency = {conc} Clients ({conc * requests_per_client} Total Requests) ---")
        latencies_ms = []
        errors = 0

        def send_requests(worker_id: int):
            c_worker = TestClient(app, cookies={"sentinel_session": cookie_val})
            local_lats = []
            local_errs = 0
            for i in range(requests_per_client):
                ep = endpoints[i % len(endpoints)]
                t0 = time.perf_counter()
                try:
                    resp = c_worker.get(ep)
                    dur_ms = (time.perf_counter() - t0) * 1000.0
                    if resp.status_code in (200, 404):  # 404 is valid for empty DB lookups
                        local_lats.append(dur_ms)
                    else:
                        local_errs += 1
                except Exception:
                    local_errs += 1
            return local_lats, local_errs

        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=conc) as executor:
            futures = [executor.submit(send_requests, w) for w in range(conc)]
            for fut in concurrent.futures.as_completed(futures):
                lats, errs = fut.result()
                latencies_ms.extend(lats)
                errors += errs
        total_time_s = time.perf_counter() - t_start

        n = len(latencies_ms)
        sorted_lats = sorted(latencies_ms) if n > 0 else [0.0]
        mean_l = sum(sorted_lats) / max(1, n)
        p50 = sorted_lats[int(n * 0.50)] if n > 0 else 0.0
        p95 = sorted_lats[min(n - 1, int(n * 0.95))] if n > 0 else 0.0
        p99 = sorted_lats[min(n - 1, int(n * 0.99))] if n > 0 else 0.0
        rps = (n / total_time_s) if total_time_s > 0 else 0.0

        print(f"  Throughput: {rps:>6.1f} req/s | Mean: {mean_l:>5.2f}ms | P50: {p50:>5.2f}ms | P95: {p95:>5.2f}ms | Errors: {errors}")

        benchmark_results["concurrency_levels"][str(conc)] = {
            "concurrent_clients": conc,
            "total_requests": n + errors,
            "successful_requests": n,
            "errors": errors,
            "rps": round(rps, 1),
            "mean_ms": round(mean_l, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2)
        }

    out_p = Path(output_json)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(benchmark_results, f, indent=2)
    print(f"\nSaved API load benchmark JSON to {output_json}")
    print("==================================================")
    return benchmark_results


if __name__ == "__main__":
    run_api_load_benchmark()
