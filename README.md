# SentinelTrack 🚗🔍

**SentinelTrack** is an enterprise-grade, high-throughput city-scale vehicle intelligence and Automated Number Plate Recognition (ANPR) tracking platform engineered for high-concurrency CCTV and smart traffic networks.

---

## 🏛️ System Architecture

`	ext
SENTINEL STREAM INGESTION (RTSP / HLS / WebRTC)
                      │
                      ▼
 00_FOUNDATION: Stream Probe & PTS-Preserving Decoder (PostgreSQL/PostGIS)
                      │
                      ▼
 01_VEHICLE_DETECTION: YOLO11 Vehicle Detector (Car, Truck, Bus, Motorcycle)
                      │
                      ▼
 02_TRACKING: Single-Camera ByteTrack (Isolated Per-Camera State & Gap Reset)
                      │
                      ▼
 03_PLATE_DETECTION: Padded Vehicle Cropper + 960px Magnifier + Dedicated Plate YOLO
                      │
                      ▼
   [NEXT: 04_PLATE_OCR -> 05_TARGET_MATCHING -> 06_VEHICLE_REID -> 07_ROUTE_ENGINE]
`

---

## 🚀 Priority Stages Implemented

### Priority 0: Foundation & Ingestion
* **Catalogue Client & Resilient Parser**: Multi-key parser with automated schema tolerance.
* **PostgreSQL / PostGIS Registry**: Spatial storage with ST_MakePoint, health event audit logs, and ON CONFLICT upserts.
* **Dual Transport Decoder**: RTSP/TCP with automated fallback to HLS/HTTPS.
* **PTS & Epoch Preservation**: Uses hardware CAP_PROP_POS_MSEC and tracks stream loops via stream_epoch.

### Priority 1: Vehicle Detection
* **Vehicle Filtering**: Exclusively passes COCO vehicle classes (car, motorcycle, us, 	ruck).
* **PTS-Based Sampling**: \text{ ms}$ interval sampling for stable inference throughput.
* **Hardware Benchmarking**: Optimized for GPU acceleration with low VRAM footprint.

### Priority 2: Single-Camera Vehicle Tracking
* **Isolated Camera Registry**: Independent ByteTrack instances per camera feed to prevent ID collisions.
* **Epoch & Gap Reset Safeguards**: Automatically invalidates tracks on stream restarts or PTS gaps $> 1500\text{ ms}$.
* **Track Lifecycle & Trails**: Tracks age, motion center history, and bounding box progression.

### Priority 3: License Plate Detection
* **Padded Vehicle Cropping**: Extracts vehicle ROIs with \%$ margin to protect bumper edges.
* **High-Resolution Magnification**: Dynamically scales crops to \text{ px}$ before plate localization.
* **Dedicated Single-Class Plate Model**: Enforces {0: 'license_plate'} contract, rejecting generic COCO false positives.
* **Coordinate Re-Projection**: Accurately projects local crop coordinates back to full  \times 1080$ CCTV space.
* **Quality & Top-K Accumulation**: Evaluates sharpness (Laplacian variance), contrast, and retains the top candidate crops per track.

---

## 🛠️ Setup & Installation

### 1. Clone Repository & Create Environment
`ash
git clone https://github.com/mdshoaibuddinchanda/sentineltrack.git
cd sentineltrack

# Create and activate Python 3.12 environment
conda create -n py312 python=3.12 -y
conda activate py312
pip install -r requirements.txt
`

### 2. Environment Configuration
Copy the sample environment file:
`ash
cp .env.example .env
`
Edit .env with your Sentinel host and PostgreSQL credentials.

### 3. Start Database
`ash
docker run -d --name sentinel-postgres -p 5432:5432 -e POSTGRES_USER=sentinel -e POSTGRES_PASSWORD=sentinel_dev -e POSTGRES_DB=sentinel postgis/postgis:16-3.4
`

---

## 🧪 Testing & Validation

Run the automated test suite (31 tests):
`ash
python -m pytest -v
`

### Stream Validation Scripts
* **Probe All Feeds:**
  `ash
  python -m 00_foundation.scripts.probe_all
  `
* **Watch Stream:**
  `ash
  python -m 00_foundation.scripts.watch_camera 1
  `
* **Real-Time Vehicle Tracker:**
  `ash
  python -m 02_tracking.scripts.test_stream 1
  `
* **Real-Time Plate Detector with Quality Overlay:**
  `ash
  python -m 03_plate_detection.scripts.test_stream 1
  `

---

## 📄 License
Proprietary / Competition Submission.
