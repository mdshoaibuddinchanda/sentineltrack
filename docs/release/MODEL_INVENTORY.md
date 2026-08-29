# Model inventory

This inventory distinguishes the four selected operational models from local-only historical and experimental artifacts. Model binaries are ignored by Git; paths below describe a provisioned checkout and are verified by `models/manifest.json` and `tools/preflight.py`.

## Operational runtime set

| Consumer | Architecture/version | Canonical file | Required | SHA-256 |
| --- | --- | --- | --- | --- |
| P1 vehicle detection | YOLO11m / Ultralytics 8.3.235 | `models/vehicle/yolo11m.pt` | Yes | `d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95` |
| P3 plate detection | Selected P11.5 clean YOLO11s single-class candidate | `models/plate/yolo11s_plate_v2.pt` | Yes | `ede0b69bba65472eff10fc29250f58b352a3a79be73aa1b93f435f8533bac3c1` |
| P4 plate OCR | PP-OCRv5 Mobile recognition ONNX | `models/ocr/PP-OCRv5_mobile_rec_infer.onnx` | Yes | `4e16deb22c4da6468bdca539b2cd3c8687825538b67109177c47d359ab994cd7` |
| P6 appearance fallback | torchvision MobileNetV3-Small ImageNet V1, 576-D | `models/reid/mobilenet_v3_small-047dcff4.pth` | Optional | `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f` |

P6 uses BGR-to-RGB conversion, `224x224` area resize, ImageNet mean/std normalization, L2-normalized pooled features, and plate-region masking whenever a local plate box exists. The checkpoint is an appearance-retrieval baseline, not a vehicle-domain ReID claim.

The required P4 support dictionary `models/ocr/ppocr_mobile_dict.txt` is also hash-verified by the manifest; it is a runtime asset rather than a separate model.

## Historical and experimental families

The local audit found 74 model/checkpoint artifacts across canonical folders, root downloads, `weights/`, `runs/`, and experiment output. They include:

- P11.5 P1/P3 candidates, OBB candidates, synthetic/real-only runs, and `mlflow` checkpoints under ignored `runs/`.
- Root YOLO11n/s/m/l, YOLO11s-OBB, and YOLO26 downloads when present locally.
- Legacy P3 `production/best.pt` and `baseline/best.pt`, retained as ignored archive material when present.
- The selected P3 candidate originally under `runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt`; release setup promotes a verified copy to the canonical P3 path.

Historical P11.5 model-selection context is retained in [`reports/p11_5/model_manifest_evidence.yaml`](../../reports/p11_5/model_manifest_evidence.yaml). `runs/` is not a production dependency and is not included in the operational manifest.

## Provisioning and integrity

```text
python scripts/setup_models.py
python scripts/setup_models.py --verify-only
python tools/preflight.py
```

Public P1 and P4 artifacts can be provisioned and hash-verified. The project-trained P3 artifact must be supplied through the competition/development artifact channel; setup fails clearly if it is absent. P6 is optional and produces a warning when absent. Server OCR and YOLO26 remain outside the operational set.
