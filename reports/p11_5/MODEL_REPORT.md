# P11.5 model report

## Environment and artifact identity

- Git starting/ending SHA: `23f575d1ab13b6ce99879763bee4ebdaae864416`.
- Remote `origin/main` at audit time: same SHA.
- Environment: conda `PY312`, Python 3.12.12, Windows 11.
- GPU: NVIDIA GeForce RTX 3050 Laptop GPU, 4,294,443,008 bytes VRAM, compute capability 8.6.
- Torch CUDA is available. ONNX Runtime exposes Azure and CPU providers only; no CUDAExecutionProvider was available.

## Current measured detector baseline

The current P3 artifact is `models/plate/production/best.pt`, SHA-256
`8603afbc9ee2c16f99971898ae98211048c01cc6668bc5d5cc46df13d5f9c8ba`. On the
locked `datasets/plate_detection/test` split it measured 147 true positives,
28 false positives, and 22 false negatives over 169 ground-truth plates:

- precision: 0.8400
- recall: 0.8698
- F1: 0.8547
- standard-aspect recall: 0.9706
- square/tall recall: 0.7164
- plates below 60 px: 0.0000 (3 examples)

The local CUDA single-frame probe at 640px, FP32, batch 1 measured p50 14.883
ms, p95 17.492 ms, and 63.774 FPS. This is an inference probe, not a camera
capacity guarantee.

## P1 status

The existing vehicle artifact is `models/vehicle/yolo11m.pt`, SHA-256
`d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95`. No
vehicle-labelled ground-truth evaluation set exists locally. The existing
25-frame vehicle probe is latency-only (p50 51.72 ms, p95 58.49 ms, 11.14 FPS)
and cannot support accuracy or tournament claims. YOLO11/YOLO26 P1 variants are
therefore `NOT_EVALUATED`.

## OBB status

The OBB derivative is ready for training, but no YOLO11-OBB or YOLO26-OBB model
has been trained, evaluated, or promoted. There is no OBB winner.

## Promotion decision

P3 remains the measured local detector baseline. No P11.5 detector improvement
is promoted because no challenger has a locked evaluation result against the
same test split.
