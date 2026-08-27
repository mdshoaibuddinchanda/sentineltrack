# SentinelTrack Reproducibility & Environment Guide

**Target Python Version:** Python 3.12.x  
**Primary Compute Framework:** PyTorch 2.5.1 + CUDA 12.1  
**Target Hardware Tested:** NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM) / Datacenter NVIDIA GPUs  
**Operating System:** Windows / Linux (Debian/Ubuntu)

---

## 1. Environment Setup

`ash
# 1. Create Conda / Virtual Environment
conda create -n sentineltrack python=3.12 -y
conda activate sentineltrack

# 2. Install PyTorch with CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 3. Install SentinelTrack Dependencies
pip install ultralytics onnxruntime psutil pyyaml psycopg[binary] av opencv-python pytest
`

---

## 2. Running Test Suites & Benchmarks

`ash
# Run full automated test suite (P0 -> P5)
pytest -v

# Run End-to-End Pipeline Profiler
python -m tools.profile_pipeline

# Run System Soak & Failure Injection Tests
python -m tools.soak_test

# Run P5 Target Matching & Shortlist Recall Benchmarks
python -m 05_target_matching.benchmark
`
