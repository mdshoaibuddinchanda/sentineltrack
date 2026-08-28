# SentinelTrack CI Findings & Diagnostic Ledger

## Run Context
- **Repository:** `mdshoaibuddinchanda/sentineltrack`
- **Starting Git SHA:** `0fe53136a5b0bafa372c78b53d7750888728ee8b`
- **GitHub Run ID:** `33194679904`
- **Frontend Job:** SUCCESS (vitest 47/47, typecheck clean, lint clean, build clean)
- **Database Container:** HEALTHY (PostGIS 17-3.5)
- **Schema Initialization:** SUCCESS (`tools/p11/init_schema.py`)
- **Backend Job:** FAILURE (105 passed, 2 failed)

---

## Root Causes

### 1. Optional OCR Dependency Leakage (Pillow / PIL)
- **Failed Test:** `10_security/tests/test_audit_compensation.py::test_target_create_audit_failure_compensation`
- **Exception:** `ModuleNotFoundError: No module named 'PIL'`
- **Import Trace:**
  `08_backend.services.target_service` -> `05_target_matching.watchlist` -> `05_target_matching.normalizer` -> `04_plate_ocr.normalization` -> `04_plate_ocr/__init__.py` -> `04_plate_ocr.pipeline` -> `04_plate_ocr.recognizers.__init__` -> `04_plate_ocr.recognizers.trocr_rec` -> `from PIL import Image` (fails when Pillow is not installed).
- **Architectural Resolution:**
  - Decouple `04_plate_ocr/__init__.py` so it only imports lightweight data models and normalization utilities; `PlateOCRPipeline` and recognizer factories are resolved lazily.
  - Decouple `04_plate_ocr/recognizers/__init__.py` so concrete recognizer implementations (`TrOCRPlateRecognizer`, `EasyOCRPlateRecognizer`, `PPOCRPlateRecognizer`, etc.) are imported only when requested by name in `get_recognizer()` or via lazy `__getattr__`.
  - Decouple `05_target_matching/__init__.py` so `TargetMatchingPipeline` is lazy and normalization/watchlist operations do not load OCR inference engines.

### 2. FastAPI Route Invariant Dependency on Framework Internals
- **Failed Test:** `10_security/tests/test_complete_route_auth_matrix.py::test_d15_policy_coverage_invariant`
- **Exception:** `AssertionError: Stale routes in ROUTE_POLICY that do not exist in application`
- **Root Cause:**
  - `test_d15_policy_coverage_invariant` iterated over `_backend.app.routes` checking `isinstance(route, APIRoute)`.
  - In newer FastAPI releases (>= 0.137, such as 0.141.1 on CI runner), included sub-routers are structured as hierarchical route trees rather than flat `APIRoute` instances in `app.routes`.
  - When `isinstance(route, APIRoute)` was checked directly on `app.routes`, only root routes were captured, resulting in an empty set of API sub-routes and falsely flagging all `ROUTE_POLICY` routes as stale.
- **Architectural Resolution:**
  - Implement robust OpenAPI-based route extraction via `_backend.app.openapi()` combined with a recursive route-tree walker fallback.
  - Add sanity checks ensuring known routes (`/api/v1/auth/login`, `/health`, `/api/v1/cameras`) are always discovered before policy comparison.
  - Preserve 100% strictness: Every discovered HTTP method/path must match `ROUTE_POLICY`.

### 3. API Process Role Coupling & Unpinned CI Dependencies
- **Resolution:**
  - Guard `08_backend/lifecycle.py` so `analytics_service` is only imported when `SENTINEL_PROCESS_ROLE` is `all` or `analytics`.
  - Create `requirements-ci.txt` and `constraints-ci.txt` to lock tested, stable dependencies across CI runs.
  - Set `SENTINEL_PROCESS_ROLE=api`, `SENTINEL_REQUIRE_GPU=false`, and `SENTINEL_PG_EVENT_BRIDGE=false` in CI backend workflow.
