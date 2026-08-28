P11.5 MAXIMUM-ACCURACY FINAL REPORT

STARTING SHA: 23f575d1ab13b6ce99879763bee4ebdaae864416
ENDING SHA: 23f575d1ab13b6ce99879763bee4ebdaae864416 (working-tree additions are isolated P11.5 tooling/reports; no commit created)
REMOTE MAIN SHA: 23f575d1ab13b6ce99879763bee4ebdaae864416

HARDWARE USED: Windows 11, conda PY312 / Python 3.12.12, Intel 8 logical CPUs, NVIDIA GeForce RTX 3050 Laptop GPU, 4,294,443,008 bytes VRAM, compute capability 8.6. Torch CUDA available; ONNX Runtime CPU provider used for OCR.

============================================================
DATASET
============================================================

RAW SOURCES: 13,082 audit records across the two archives, frozen exports, archive image/label folders, Google XML, State-wise OLX XML, video frames/XML, and OCR crops; 13,081 image records plus one orphan XML.
CANONICAL V1: plate_detection 2,531 images (train 2,035 / val 329 / test 167); plate_ocr 1,707 crops (train 1,382 / val 147 / test 178).
DETECTION V2: 5,281 unique images (train 4,162 / val 775 / test 344), 967 exact duplicate candidates excluded; not trained.
OCR V2: train 1,396 / expanded val 150 / preserved locked test 178; 17 new identity groups added; not trained.
MULTIFRAME V1: NOT BUILT; sequence-capable video source is inventoried, but no locked frame-level OCR track was available.
SYNTHETIC V1: 8-example deterministic smoke corpus, seed 115; not used for accuracy claims or training.

EXACT DUPLICATES: 3,531 groups / 9,593 records.
NEAR-DUPLICATE GROUPS: 3,514 pHash candidate groups.
INVALID/QUARANTINED: 137 flagged records, including 62 missing labels, empty annotations, invalid geometry, one orphan XML, invalid text, and three extension/byte-format mismatches.
UNLABELED RESOLUTION: 62 archive images remain excluded; no labels were invented.

IDENTITY LEAKAGE:
PASS / FAIL: PASS for frozen OCR identities and canonical detection split hashes; V2 grouping also has zero train/val/test identity overlap.

LEGACY DATASETS UNCHANGED:
YES / NO: YES. P11.5 reads the frozen datasets and writes only isolated derivatives/manifests/reports; source data was not rewritten.

============================================================
BASELINE
============================================================

P1 MODEL: YOLO11m vehicle artifact `models/vehicle/yolo11m.pt`; accuracy NOT EVALUATED because no vehicle ground-truth corpus exists. Existing 25-frame operational probe is latency-only: 51.72 ms p50 / 58.49 ms p95 / 11.14 FPS.
P3 MODEL: Current custom YOLO11s artifact `models/plate/production/best.pt`; SHA-256 `8603afbc9ee2c16f99971898ae98211048c01cc6668bc5d5cc46df13d5f9c8ba`.
OCR MODEL: PP-OCRv5 mobile ONNX baseline selected; SHA-256 `4e16deb22c4da6468bdca539b2cd3c8687825538b67109177c47d359ab994cd7`.

P3 METRICS: 147 TP / 28 FP / 22 FN over 169 plates; precision 0.8400, recall 0.8698, F1 0.8547. Standard-aspect recall 0.9706; square/tall recall 0.7164; below-60px recall 0.0000.

OCR LEGACY VAL: Mobile post exact 0.6463, character accuracy 0.8465, CER 0.1064, p50/p95 10.92/25.50 ms. Server post exact 0.6463, character accuracy 0.7944, CER 0.1470, p50/p95 437.83/575.91 ms.
OCR LEGACY TEST: Mobile post exact 0.5787, character accuracy 0.7839, CER 0.1557, p50/p95 10.53/24.85 ms. Server post exact 0.5787, character accuracy 0.7721, CER 0.1652, p50/p95 413.81/594.96 ms.

END-TO-END: NOT EVALUATED; no locked vehicle-labelled end-to-end benchmark with full-stream ground truth.

============================================================
P1 TOURNAMENT
============================================================

YOLO11m: NOT EVALUATED — no vehicle ground-truth evaluation set.
YOLO11l: NOT EVALUATED — challenger artifact/result not present.
YOLO11x: NOT EVALUATED — challenger artifact/result not present.

YOLO26m: NOT EVALUATED — no vehicle ground-truth evaluation set or measured artifact.
YOLO26l: NOT EVALUATED — no vehicle ground-truth evaluation set or measured artifact.
YOLO26x: NOT EVALUATED — no vehicle ground-truth evaluation set or measured artifact.

P1 WINNER: NONE.
REASON: Accuracy promotion would be unsupported without a legitimate locked vehicle-labelled benchmark.

============================================================
P3 TOURNAMENT
============================================================

YOLO11s: CURRENT BASELINE ONLY — measured as the existing custom P3 artifact.
YOLO11m: NOT EVALUATED.
YOLO11l: NOT EVALUATED.
YOLO11x: NOT EVALUATED.

YOLO26s: NOT EVALUATED.
YOLO26m: NOT EVALUATED.
YOLO26l: NOT EVALUATED.
YOLO26x: NOT EVALUATED.

OBB RESULT: Derivative labels ready for 5,281 images; no OBB model trained.

P3 WINNER: Current custom YOLO11s baseline remains the only measured candidate.
REASON: No challenger has a same-split locked result.

============================================================
OCR TOURNAMENT
============================================================

PP-OCRv5 Mobile: MEASURED; selected current baseline.
PP-OCRv5 Server: MEASURED; tied exact test but slower and lower character accuracy.
SVTRv2: NOT EVALUATED.
RepSVTR: NOT EVALUATED.
PARSeq: NOT EVALUATED.
MGP-STR: NOT EVALUATED.
OTHER CHALLENGERS: NOT EVALUATED.

BEST PRETRAINED: PP-OCRv5 Mobile for the current accuracy/latency tradeoff.
BEST FINE-TUNED: NONE.

LEGACY TEST EXACT: 0.5787 mobile postprocessed; 0.5787 server postprocessed.
EXPANDED TEST EXACT: NOT EVALUATED.
CHAR ACCURACY: 0.7839 mobile / 0.7721 server on locked test.
CER: 0.1557 mobile / 0.1652 server on locked test.

BASELINE → WINNER EXACT DELTA: 0.0000 between selected mobile baseline and server alternative; no trained challenger delta measured.

============================================================
TEMPORAL
============================================================

SINGLE FRAME: NOT EVALUATED in a locked frame-level track.
CURRENT VOTER: IMPLEMENTED, NOT EVALUATED.
BEST-3: NOT EVALUATED.
BEST-5: NOT EVALUATED.
BEST-8: NOT EVALUATED.
CHARACTER FUSION: NOT EVALUATED.
LOGIT FUSION: NOT EVALUATED.
LEARNED FUSION: NOT EVALUATED.

TEMPORAL WINNER: NONE.
REASON: Video frames are inventoried, but the frozen corpus lacks a defined locked frame-level OCR ground-truth track.

============================================================
QUALITY / CROP / RECOGNITION
============================================================

CROP MARGIN: NOT EVALUATED.
RECTIFICATION: NOT EVALUATED.
STN: NOT EVALUATED.
CLASSICAL ENHANCEMENT: NOT EVALUATED.
SUPER-RESOLUTION: NOT EVALUATED.

PROMOTED: None.
REJECTED: No candidate is rejected for poor accuracy without a fair locked comparison; unmeasured candidates remain open.

============================================================
STRUCTURE-AWARE DECODING
============================================================

RAW OCR: Mobile and server raw/postprocessed baselines measured.
STRUCTURE-AWARE: NOT EVALUATED as a separate candidate.
DELTA: NOT MEASURED.
FALSE-CORRECTION RATE: NOT MEASURED.

============================================================
END-TO-END
============================================================

BEST PIPELINE: Existing production pipeline with current measured P3 and mobile OCR components; joint end-to-end result NOT EVALUATED.
VEHICLE RECALL: NOT MEASURED.
PLATE RECALL: 0.8698 for the isolated P3 locked detector test.
PLATE EXACT: NOT MEASURED end-to-end.
TRACK EXACT: NOT MEASURED.

TARGET PRECISION: NOT MEASURED against a full end-to-end target set.
TARGET RECALL: NOT MEASURED against a full end-to-end target set.
TARGET F1: NOT MEASURED against a full end-to-end target set.
TARGET FPR: NOT MEASURED.

P50: P3 detector probe 14.883 ms; mobile OCR locked test 10.53 ms per crop.
P95: P3 detector probe 17.492 ms; mobile OCR locked test 24.85 ms per crop.
VRAM: 4,294,443,008 bytes total local GPU VRAM.
THROUGHPUT: P3 detector probe 63.774 FPS; mobile OCR locked test 79.54 crops/s.

============================================================
PROFILES
============================================================

BASELINE:
P1: YOLO11m existing artifact.
P3: Current custom YOLO11s artifact.
OCR: PP-OCRv5 Mobile.
TEMPORAL: Current voter implementation, not evaluated.

DEVELOPMENT:
P1: Same validated artifacts as baseline.
P3: Same validated artifacts as baseline.
OCR: Same validated artifacts as baseline.
TEMPORAL: Current voter implementation, not evaluated.

CLOUD_BALANCED:
P1: UNAVAILABLE_NOT_BENCHMARKED.
P3: UNAVAILABLE_NOT_BENCHMARKED.
OCR: UNAVAILABLE_NOT_BENCHMARKED.
TEMPORAL: UNAVAILABLE_NOT_BENCHMARKED.

CLOUD_ACCURACY:
P1: UNAVAILABLE_NOT_BENCHMARKED.
P3: UNAVAILABLE_NOT_BENCHMARKED.
OCR: UNAVAILABLE_NOT_BENCHMARKED.
TEMPORAL: UNAVAILABLE_NOT_BENCHMARKED.

AUTO PROFILE: IMPLEMENTED.
BEHAVIOR: Resolves cloud profiles only when validated artifacts exist and hardware gates pass; on this machine it falls back to development, then baseline.

============================================================
CAPACITY
============================================================

HARDWARE: NVIDIA GeForce RTX 3050 Laptop GPU, 4,294,443,008 bytes VRAM.
PROFILE: baseline local probe.
1 STREAM: NOT MEASURED.
5 STREAMS: NOT MEASURED.
10 STREAMS: NOT MEASURED.
25 STREAMS: NOT MEASURED.
50 STREAMS: NOT MEASURED.

LOCAL MEASURED: P3 single-frame probe only.
TARGET-SERVER MEASURED: NOT MEASURED.
PROJECTED: NOT REPORTED.

============================================================
MODEL MANIFEST
============================================================

MODEL: vehicle detector / plate detector / PP-OCRv5 mobile and server.
PATH: See `configs/model_manifest.yaml` and `experiments/p11_5/registry.csv`.
SHA256: Recorded for every existing artifact; see registry.
RUNTIME: Ultralytics/PyTorch for detection; ONNX Runtime CPU for OCR.
PRECISION: FP32.
LICENSE: Roboflow detector source is CC-BY-4.0; several archive sources remain UNKNOWN or LICENSE_UNVERIFIED.
SOURCE: Existing SentinelTrack artifacts plus audited local datasets.

============================================================
INTEGRATION / CI
============================================================

BACKEND: Existing production backend untouched; P11.5 utilities are isolated under `tools/p11_5`.
SECURITY/SCALE: No API import path was changed; cloud scale and multi-stream capacity remain unmeasured.
CI CONTRACT: Seven isolated P11.5 tests pass under PY312. Full repository CI was not rerun in this evidence pass.
FRONTEND: Unchanged.
TYPECHECK: NOT RUN.
LINT: NOT RUN.
BUILD: NOT RUN.

FINAL GITHUB ACTIONS RUN ID: NOT RUN.
HEAD SHA: 23f575d1ab13b6ce99879763bee4ebdaae864416.
STATUS: OPEN.
CONCLUSION: Dataset audit, provenance manifests, duplicate/leakage controls, derivative datasets, baseline evidence, profile resolver, synthetic smoke generator, temporal helper, benchmark tool, and isolated tests are complete. Accuracy-tournament, fine-tuning, end-to-end, cloud, and multi-stream gates remain unverified.

============================================================
REGRESSIONS
============================================================

P0-P11 REGRESSIONS: No source or production-file changes detected from this work.
P5 FALSE-POSITIVE REGRESSION: NOT MEASURED beyond the existing P3 locked result.
P10 SECURITY REGRESSION: No API import path or security configuration changed.
P11 SCALE REGRESSION: NOT MEASURED; cloud and stream-load tests remain open.

P6: NOT IN SCOPE per P11.5 prohibitions.
P12: NOT IN SCOPE; this report does not claim submission readiness.

FINAL VERDICT: OPEN.

PRIORITY 11.5 REMAINS OPEN — BLOCKERS: no vehicle-labelled P1 benchmark; no trained/evaluated V2, OBB, or OCR-fine-tuned challengers; no locked frame-level OCR track for temporal evaluation; no full end-to-end benchmark; and no target-cloud or multi-stream capacity measurements.
