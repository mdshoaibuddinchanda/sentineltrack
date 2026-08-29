# SentinelTrack P12 — Authoritative Evidence Inventory

This inventory is the source-of-truth map for the submission package. It was
assembled from the frozen repository at commit
`1f48aad81a35553ff1e80866a17b1784313efa1b` and the official Gujarat Sentinel
website accessed on 30 August 2026.

## Evidence labels

| Label | Meaning |
|---|---|
| `MEASURED_LOCAL` | Measured on the local PY312/RTX 3050 workstation or local runtime. |
| `MEASURED_TEST` | Measured by a deterministic test or locked evaluation population. |
| `SIMULATED` | Generated fixtures, proxy data, or a controlled simulation; not field evidence. |
| `PROJECTED` | Derived from stated planning assumptions; not measured deployment capacity. |
| `ASSUMPTION` | An explicit planning input used for scenario sizing. |
| `NOT_MEASURED` | The repository deliberately does not claim this quantity. |
| `OFFICIAL_SOURCE` | Requirement or fact published by the challenge organizer, not a SentinelTrack performance result. |

## Frozen engineering and model evidence

| Claim or decision | Value | Classification | Authoritative source |
|---|---|---|---|
| P12 base | `1f48aad81a35553ff1e80866a17b1784313efa1b` | `MEASURED_TEST` | Git history; P6 exact CI run `33274638726` |
| Python runtime | PY312, Python 3.12.12 | `MEASURED_LOCAL` | `reports/p11_5/model_manifest_evidence.yaml`; local audit |
| Local hardware | NVIDIA RTX 3050 Laptop GPU, 4096 MiB, CUDA 12.1, PyTorch 2.5.1+cu121 | `MEASURED_LOCAL` | `reports/p11_5/model_manifest_evidence.yaml`; P6 benchmark |
| P1 detector | YOLO11m | `MEASURED_LOCAL` | `models/manifest.json`; `reports/p11_5/MODEL_REPORT.md` |
| P1 external vehicle accuracy | No authoritative vehicle GT available | `NOT_MEASURED` | `reports/p11_5/MODEL_REPORT.md` |
| P3 production detector | F1 `0.940984` | `MEASURED_TEST` | `reports/p11_5/detector_eval/baseline-production-strict-640_test_640.json` |
| P3 selected YOLO11s candidate | TP `300`, FP `10`, FN `5`, F1 `0.975610`, mAP50-95 `0.783111` | `MEASURED_TEST` | `reports/p11_5/detector_eval/p3-yolo11s-v2-e20-b4-640-r3-clean-authoritative_test_640.json` |
| Plate recognition chain | TP `143`, FP `4`, FN `0`, F1 `0.986207`; OCR exact `49/143 = 0.3427`; CER `0.2662`; throughput `33.51 FPS` | `MEASURED_TEST` | `reports/p11_5/end_to_end_evaluation.json` |
| OCR production model | PP-OCRv5 Mobile ONNX | `MEASURED_LOCAL` | `models/manifest.json`; `reports/plate_ocr/ppocr_mobile_test_evaluation.json` |
| OCR locked test readout | P50 `10.53 ms`, P95 `24.85 ms`, `79.54` crops/s | `MEASURED_TEST` | `reports/plate_ocr/ppocr_mobile_test_evaluation.json` |
| OCR fine-tuning | Attempt stopped resource-limited; no checkpoint or result | `NOT_MEASURED` | `reports/p11_5/OCR_FINETUNE.md` |
| P2 tracking identity | Per-camera `(camera_id, stream_epoch, track_id)` with reset on discontinuity | `MEASURED_TEST` | `docs/p11_runtime_mainframe.md`; `02_tracking/`; tests |
| P5 controlled watchlist benchmark | Recall@100 `92.0%`, P95 `112.55 ms` at 100k records | `MEASURED_TEST` | `docs/system_optimization_baseline.md`; `reports/target_matching/` |
| P7 route semantics | Chronological camera sightings, geodesic lower bound, required speed and feasibility; no road routing | `MEASURED_TEST` | `docs/priority7_baseline.md`; `07_route_engine/` |
| P8 API benchmark | Endpoint-specific local P50/P95 values in frozen baseline | `MEASURED_LOCAL` | `docs/priority8_baseline.md` |
| P9 UI verification | Frozen baseline records typecheck, lint, frontend tests and build | `MEASURED_TEST` | `docs/priority9_baseline.md`; P12 final validation |
| P10 controls | Opaque session cookie, Argon2id, CSRF, RBAC, audit, rate limiting and WebSocket authorization | `MEASURED_TEST` | `docs/priority10_baseline.md`; `docs/security/`; `10_security/tests/` |
| P11 sampling | Base `1 FPS`, burst `5 FPS`, bounded queues and stale-frame dropping | `MEASURED_TEST` | `11_scale_deployment/config.py`; `docs/p11_runtime_mainframe.md`; tests |
| P11 safe statewide capacity | Not measured; no single-frame or local-node result is converted into safe camera capacity | `NOT_MEASURED` | `reports/p11_5/CAPACITY_DELTA.md` |
| P6 appearance model | MobileNetV3-Small ImageNet, 576-D, L2 normalized, checkpoint SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f` | `MEASURED_LOCAL` | `models/manifest.json`; `reports/p6/P6_BENCHMARK.json` |
| P6 plate masking | Plate region masked by default; OCR text never enters ReID | `MEASURED_TEST` | `06_vehicle_reid/extractor.py`; `tests/test_p6_vehicle_reid.py` |
| P6 identity ground truth | No verified true cross-camera vehicle-ID GT | `NOT_MEASURED` | `reports/p6/P6_REPORT.md`; `reports/p6/P6_EVALUATION.json` |
| P6 proxy evaluation | 240 samples; 61 calibration tracks and 27 locked tracks with no track overlap | `MEASURED_TEST` / `SIMULATED` | `reports/p6/P6_EVALUATION.json` |
| P6 calibrated threshold | `0.874001`; calibration FMR `0.007246`, FNMR `0.458065`; locked proxy FMR `0`, FNMR `0.459016` | `MEASURED_TEST` / `SIMULATED` | `reports/p6/P6_EVALUATION.json` |
| P6 appearance escalation | Review-only; no appearance-only HIGH/CRITICAL alert or exact identity claim | `MEASURED_TEST` | `06_vehicle_reid/fusion.py`; `06_vehicle_reid/matcher.py`; P6 tests |
| P6 extractor throughput | Batch 1 `110.65`, batch 4 `292.97`, batch 8 `391.85` embeddings/s | `MEASURED_LOCAL` | `reports/p6/P6_BENCHMARK.json` |
| P6 gallery search | P50: 100=`1.62 ms`, 1,000=`13.61 ms`, 10,000=`166.56 ms` | `MEASURED_LOCAL` | `reports/p6/P6_BENCHMARK.json` |
| Existing metadata storage reference | 50-camera example `~75 MB/day`, `~2.25 GB/month` | `ASSUMPTION` | `docs/deployment/retention_and_growth.md` |
| 80k deployment node counts | Scenario outputs in P12 are planning calculations only | `PROJECTED` / `ASSUMPTION` | `12_submission/ROLLOUT_80K_CAMERAS.md` |

## Official challenge evidence

| Official claim | Classification | Source |
|---|---|---|
| Model 1 CCTV registry/GIS foundation is compulsory | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/faqs> |
| Test case uses approximately 50 geographically distributed simulated feeds | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/faqs> |
| Expected vehicle output includes complete route and timestamped, location-wise movement history | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/faqs> |
| HLD must cover heterogeneous cameras/VMS, bandwidth, analytics, ~80,000-camera scale and department details | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/faqs> |
| Submission includes presentation and HLD; videos must show working software | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/faqs> |
| Official schedule: registration opened 4 August 2026; submission deadline 7 September 2026; event 10–11 September 2026 | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/schedule> |
| Phase 1 sandbox and Phase 2 production round; six teams advance | `OFFICIAL_SOURCE` | <https://sentinel.gujarat.gov.in/phases> |

## Evidence discipline

P12 never converts `NOT_MEASURED`, `ASSUMPTION`, `SIMULATED`, or `PROJECTED`
values into achieved production performance. The local 50-camera, 80k-camera,
cost, bandwidth, storage and disaster-recovery calculations are planning
scenarios and are labelled accordingly. P7 camera-to-camera lines are observed
chronological trajectories, not road-level routes.
