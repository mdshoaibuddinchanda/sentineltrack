# SentinelTrack Database Retention, Growth Model & Partitioning Architecture

## 1. Storage Estimation per Event Entity

| Entity Type | Average Row Size (Bytes) | Estimated Daily Volume (50 Cameras) | Daily Storage (50 Cameras) | Monthly Storage (50 Cameras) |
|---|---|---|---|---|
| **Vehicle Sighting** | ~350 B | ~200,000 events | ~70 MB / day | ~2.1 GB / month |
| **Target Alert** | ~500 B | ~500 alerts | ~250 KB / day | ~7.5 MB / month |
| **Audit Event** | ~400 B | ~10,000 events | ~4 MB / day | ~120 MB / month |
| **Camera Health Event** | ~200 B | ~1,000 events | ~200 KB / day | ~6 MB / month |
| **Total Aggregated** | - | ~211,500 events/day | **~75 MB / day** | **~2.25 GB / month** |

---

## 2. Configurable Data Retention Policy

SentinelTrack implements partitioned data lifecycle policies:

1. **Evidentiary Data (Sightings & Alerts)**:
   - Default retention: **90 Days** (configurable via `SENTINEL_EVIDENTIARY_RETENTION_DAYS`).
   - Sighting records older than retention period are safely archived to cold storage before purging.
2. **Operational Telemetry (Camera Health Events & Metrics)**:
   - Default retention: **14 Days**.
3. **Security Audit Log (`audit_events`)**:
   - Default retention: **365 Days** (immutable tamper-evident log; never auto-deleted without administrative authorization).

---

## 3. Future PostgreSQL Table Partitioning Strategy

For scale deployments beyond 10 million sightings:
- Partition `vehicle_sightings` by `RANGE (event_time_utc)` on a monthly basis:
  ```sql
  CREATE TABLE vehicle_sightings (
      sighting_id VARCHAR(64) PRIMARY KEY,
      camera_id VARCHAR(64) NOT NULL,
      registration_candidate VARCHAR(32) NOT NULL,
      event_time_utc TIMESTAMPTZ NOT NULL,
      ...
  ) PARTITION BY RANGE (event_time_utc);
  ```
- Fast partition dropping for retention pruning without table lock contention.
