import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import json
import uuid
import statistics
import importlib
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app
client = TestClient(app)

p5_models = importlib.import_module("05_target_matching.models")
p5_repo = importlib.import_module("05_target_matching.repository")
p7_models = importlib.import_module("07_route_engine.models")
p7_cam_repo = importlib.import_module("07_route_engine.camera_repository")

# Seed test data for realistic benchmark
cam_repo = p7_cam_repo.PostgresCameraRepository()
target_repo = p5_repo.PostgresTargetMatchingRepository()

bench_plate = "GJ01BENCHMARK"
t0 = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)

for i in range(5):
    c = p7_models.CameraGeo(f"cam_bench_{i}", f"Bench Camera {i}", 23.0100 + i*0.01, 72.5600 + i*0.01, location_quality=p7_models.LocationQuality.VERIFIED)
    cam_repo.save_camera(c)
    target_repo.save_sighting(p5_models.Sighting(
        sighting_id=str(uuid.uuid4()),
        camera_id=f"cam_bench_{i}",
        stream_epoch=1,
        track_id=100 + i,
        first_pts_ms=float(i*60000),
        last_pts_ms=float(i*60000 + 1000),
        registration_candidate=bench_plate,
        confidence=0.97,
        match_score=0.96,
        match_class=p5_models.MatchClass.EXACT,
        created_at=t0 + timedelta(minutes=i*2),
        event_time_utc=t0 + timedelta(minutes=i*2),
        event_time_source="SOURCE_WALLCLOCK",
        event_time_quality="HIGH"
    ))


def bench_endpoint(name: str, method: str, url: str, json_data=None, iterations: int = 100):
    latencies = []
    for _ in range(iterations):
        t_start = time.perf_counter()
        if method == "GET":
            res = client.get(url)
        elif method == "POST":
            res = client.post(url, json=json_data)
        t_end = time.perf_counter()
        if res.status_code in [200, 201]:
            latencies.append((t_end - t_start) * 1000.0)

    latencies.sort()
    n = len(latencies)
    return {
        "endpoint": name,
        "method": method,
        "url": url,
        "iterations": n,
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_p50_ms": round(statistics.median(latencies), 3),
        "p90_ms": round(latencies[int(n * 0.90)], 3),
        "p95_ms": round(latencies[int(n * 0.95)], 3),
        "p99_ms": round(latencies[min(int(n * 0.99), n - 1)], 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3)
    }


def run_all_benchmarks():
    print("Running SentinelTrack Priority 8 API Benchmark...")
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": [
            bench_endpoint("Liveness (/health)", "GET", "/health", iterations=100),
            bench_endpoint("Readiness (/ready)", "GET", "/ready", iterations=50),
            bench_endpoint("Metrics Snapshot (/metrics)", "GET", "/metrics", iterations=100),
            bench_endpoint("List Cameras (/api/v1/cameras)", "GET", "/api/v1/cameras?limit=50", iterations=100),
            bench_endpoint("Create Target (/api/v1/targets)", "POST", "/api/v1/targets", json_data={"registration": f"GJ01B{uuid.uuid4().hex[:4].upper()}", "priority": "HIGH"}, iterations=50),
            bench_endpoint("List Targets (/api/v1/targets)", "GET", "/api/v1/targets?limit=50", iterations=100),
            bench_endpoint("List Sightings (/api/v1/sightings)", "GET", f"/api/v1/sightings?registration={bench_plate}", iterations=100),
            bench_endpoint("Vehicle History (/api/v1/vehicles/{reg}/history)", "GET", f"/api/v1/vehicles/{bench_plate}/history", iterations=100),
            bench_endpoint("List Alerts (/api/v1/alerts)", "GET", "/api/v1/alerts?limit=50", iterations=100),
            bench_endpoint("Target Route Kinematics (/api/v1/routes/{reg})", "GET", f"/api/v1/routes/{bench_plate}?persist=false", iterations=100),
            bench_endpoint("Route GeoJSON RFC-7946 (/api/v1/routes/{reg}/geojson)", "GET", f"/api/v1/routes/{bench_plate}/geojson", iterations=100),
            bench_endpoint("Route Summary (/api/v1/routes/{reg}/summary)", "GET", f"/api/v1/routes/{bench_plate}/summary", iterations=100)
        ]
    }

    out_dir = Path("reports/backend")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "final_benchmark.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n================ BENCHMARK RESULTS ================")
    for ep in results["endpoints"]:
        print(f"{ep['endpoint']:<45} | Mean: {ep['mean_ms']:>6.2f} ms | P50: {ep['median_p50_ms']:>6.2f} ms | P95: {ep['p95_ms']:>6.2f} ms | P99: {ep['p99_ms']:>6.2f} ms")
    print(f"\nBenchmark saved to {out_file}")


if __name__ == "__main__":
    run_all_benchmarks()
