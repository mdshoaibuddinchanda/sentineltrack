# Hardcoded values audit

This is a release audit of fixed values found in runtime code, configuration, tests, documentation, and experiment tooling. A hardcoded value is acceptable when it is a model contract, safety bound, protocol default, test fixture, or reproducibility constant. Values that affect deployment behavior are exposed through configuration where practical.

| Value or pattern | Location/classification | Treatment |
| --- | --- | --- |
| `models/vehicle/yolo11m.pt` | P1 runtime default | Canonical fixed model path; hash controlled by `models/manifest.json` |
| `models/plate/yolo11s_plate_v2.pt` | P3 runtime default and validation tools | Canonical selected P11.5 model path; no `runs/` dependency |
| `models/ocr/PP-OCRv5_mobile_rec_infer.onnx` | P4 recognizer | Canonical manifest path; optional server OCR is separate |
| `models/reid/mobilenet_v3_small-047dcff4.pth` | P6 config | Canonical optional checkpoint path with SHA-256 and review-only policy |
| Ultralytics `8.3.235` | Production dependency | Deliberately pinned frozen runtime; YOLO26 `8.4.132` is optional experiment-only |
| YOLO11m/P3/P4/P6 SHA-256 values | Manifest/config/evidence | Integrity constants, not tunable inference behavior |
| P6 threshold `0.874001` and review threshold `0.80` | `configs/reid.yaml` | Calibration output retained; review-only mode prevents automatic appearance escalation |
| P6 gallery `10,000`, TTL `3600s`, top five crops | P6 config | Bounded resource/safety constants |
| P2/P3 sampling, padding, crop widths, support counts | subsystem configs/code | Algorithm and model-contract constants; existing frozen behavior retained |
| P7 speed/temporal feasibility bounds | route-engine config | Explicit lower-bound safety policy; not road routing |
| `localhost`, ports `8000`, `5173`, `5432` | demo/Docker/test defaults | Local development fixtures; deployment overrides via environment/compose |
| `sentinel_password` / test DB credentials | `.env.example`, CI fixtures | Development/test only; real secrets remain outside Git |
| `cam_*`, `target-*`, sample registrations | tests and demo fixtures | Deterministic test/presentation data, not production identities |
| absolute Windows paths in historical evidence | local reports/tool outputs | Provenance-only or stale machine-specific values; not runtime configuration |
| `runs/...` references in P11.5 tools and reports | experiment/history tooling | Kept as evidence context; runtime paths migrated to `models/manifest.json` |
| `224x224`, ImageNet mean/std, 576-D | P6 extractor/config | Model preprocessing contract |

## Resolution policy

The release cleanup removed CWD-sensitive root model defaults, removed the duplicate operational manifest, and moved dependencies to explicit files. It did not turn every reproducibility constant into a mutable setting: changing frozen thresholds or safety bounds would be a model/policy change requiring a new evaluation and is outside release cleanup.
