# SentinelTrack

**Production-oriented multi-camera vehicle intelligence and ANPR platform developed for the Sentinel Gujarat CCTV integration challenge.**

---

## System Architecture

```text
SENTINEL STREAM INGESTION (RTSP / HLS)
                  │
                  ▼
 00_FOUNDATION: Dynamic PTS Health Monitor & Unified Stream Resolver (PostGIS)
                  │
                  ▼
 01_VEHICLE_DETECTION: YOLO11 Vehicle Detector (Car, Truck, Bus, Motorcycle)
                  │
                  ▼
 02_TRACKING: Cadence-Aware ByteTrack (Isolated Per-Camera State & Gap Reset)
                  │
                  ▼
 03_PLATE_DETECTION: Padded Vehicle Cropper + 960px Magnifier + Dedicated Plate YOLO
                  │
                  ▼
   [NEXT: 04_PLATE_OCR -> 05_TARGET_MATCHING -> 06_VEHICLE_REID -> 07_ROUTE_ENGINE]
```

---

## Priority Stages Implemented

### Priority 0: Foundation & Ingestion

* **Catalogue Client & Resilient Parser**: Multi-key parser with schema fallback support.
* **PostgreSQL / PostGIS Registry**: Geospatial indexing with `ST_MakePoint`, health event logs, and `ON CONFLICT` upserts.
* **Unified Stream Resolver**: Automatic RTSP/TCP probing with seamless fallback to HLS/HTTPS.
* **Dynamic PTS Health Tracking**: Sliding-window median interval tracking avoiding static FPS assumptions.

### Priority 1: Vehicle Detection

* **Vehicle Filtering**: Passes COCO vehicle classes (`car`, `motorcycle`, `bus`, `truck`).
* **PTS-Based Sampling**: 150 ms interval sampling cadence (~6.7 FPS).
* **Hardware Benchmarking**: Optimized for GPU acceleration with low VRAM footprint.

### Priority 2: Single-Camera Vehicle Tracking

* **Isolated Camera Registry**: Independent ByteTrack instances per camera feed to prevent ID collisions.
* **Cadence-Aware Kalman Filter**: Matches ByteTrack frame rate directly to the 150 ms sampling cadence.
* **Epoch & Gap Reset Safeguards**: Automatically invalidates tracks on stream restarts or PTS gaps > 1500 ms.

### Priority 3: License Plate Detection & Provenance

* **Padded Vehicle Cropping**: Extracts vehicle ROIs with 8% margin to protect bumper edges.
* **High-Resolution Magnification**: Dynamically scales crops to 960 px before plate localization.
* **Dedicated Single-Class Plate Model**: Enforces `{0: 'license_plate'}` contract, rejecting generic COCO false positives.
* **Verified Real Dataset Workflow**: Uses open verified ANPR dataset (CC-BY-4.0) with strict **Real-Only Validation & Test** splits and zero hash overlap.
* **Coordinate Re-Projection**: Accurately projects local crop coordinates back to full 1920x1080 CCTV space.
* **Quality & Top-K Accumulation**: Evaluates sharpness (Laplacian variance), contrast, and retains the top candidate crops per track.

---

## Setup & Installation

### 1. Clone Repository & Create Environment

```bash
git clone https://github.com/mdshoaibuddinchanda/sentineltrack.git
cd sentineltrack

# Create and activate Python 3.12 environment
conda create -n py312 python=3.12 -y
conda activate py312
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit `.env` with your Sentinel host and database credentials.
*(Note: `.env.example` contains development-only default credentials for local Docker Postgres).*

### 3. Start Database

```bash
docker run -d --name sentinel-postgres -p 5432:5432 -e POSTGRES_USER=sentinel -e POSTGRES_PASSWORD=sentinel_dev -e POSTGRES_DB=sentinel postgis/postgis:16-3.4
```

### Priority 4: License Plate OCR & Multi-Frame Consensus
* **Production Recognizer:** `PP-OCRv5_mobile_rec` running via ONNX Runtime CPU with genuine tensor batching.
* **Layout Awareness:** Integrated two-line motorcycle / square plate decomposition and reassembly.
* **Soft Indian Grammar & Normalization:** Position-specific confusion discounting ($O/0, I/1, A/4, B/8, S/5, Z/2, G/6$) without global string corruption.
* **Multi-Frame Weighted Voter:** Positional character consensus requiring corroborating support count $\ge 2$ for track resolution.

---

## Setup & Installation

### 1. Clone Repository & Create Environment

```bash
git clone https://github.com/mdshoaibuddinchanda/sentineltrack.git
cd sentineltrack

# Create and activate Python 3.12 environment
conda create -n py312 python=3.12 -y
conda activate py312
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the sample environment file:

```bash
cp .env.example .env
```

Edit `.env` with your Sentinel host and database credentials.
*(Note: `.env.example` contains development-only default credentials for local Docker Postgres).*

### 3. Start Database

```bash
docker run -d --name sentinel-postgres -p 5432:5432 -e POSTGRES_USER=sentinel -e POSTGRES_PASSWORD=sentinel_dev -e POSTGRES_DB=sentinel postgis/postgis:16-3.4
```

### 4. Model Setup

Download the base vehicle detector, plate detector, and OCR recognition models:

```bash
# Vehicle and plate detectors
python scripts/setup_models.py

# Priority 4 OCR models (PP-OCRv5 Mobile & Server)
python -m 04_plate_ocr.scripts.setup_ocr_models
```

---

## Testing & Validation

Run the automated test suite (66 unit tests across Priorities 0–4):

```bash
python -m pytest -v
```

### OCR Testing & Benchmark Scripts

* **Full Quantitative Evaluation (Mobile, Server, Adaptive):**
  ```bash
  python -m 04_plate_ocr.training.evaluate
  ```

* **Latency & Batching Benchmark ($B=1, 2, 4, 8$):**
  ```bash
  python -m 04_plate_ocr.benchmark
  ```

* **Test Single Plate Crop:**
  ```bash
  python -m 04_plate_ocr.scripts.test_crop <path_to_image>
  ```

* **Live Multi-Camera Sentinel OCR Validator:**
  ```bash
  python -m 04_plate_ocr.scripts.validate_live_production
  ```

---

## License

Proprietary / Competition Submission.

