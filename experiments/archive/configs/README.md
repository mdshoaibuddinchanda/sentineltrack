# SentinelTrack Algorithm Experimentation Framework

This directory contains configuration files for machine learning, OCR, tracking, and matching experiments.

## Principles for Algorithm Experimentation

1. **Frozen Production Baseline**: Default production pipelines always inherit parameters from `reports/p11/baseline_manifest.json`.
2. **Never Overwrite Baseline In-Place**: When evaluating a new model, OCR recognizer, or tracking threshold, define a new YAML file in this directory (e.g. `exp01_finetuned_plate_detector.yaml`).
3. **Reproducible Evaluation**: Run the experiment comparator using:
   ```bash
   python experiments/archive/run.py --config experiments/archive/configs/example.yaml --output reports/experiments/exp01_results.json
   ```
4. **Metrics Tracked**:
   - Accuracy, Precision, Recall, F1 Score
   - False Positive Count
   - Latency (P50, P95, P99 in ms)
   - Throughput (FPS)
   - GPU VRAM consumption (allocated and peak in MB)
