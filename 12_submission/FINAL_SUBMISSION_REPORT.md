# SentinelTrack — Final Hackathon Submission Report

## 1. Executive Summary

SentinelTrack is a hybrid, evidence-preserving platform for multi-camera vehicle observation, plate recognition, target matching, chronological cross-camera correlation, and operator review. This package is based on the frozen P6 engineering commit and adds documentation, diagrams, runbooks, and deployment planning without reopening the frozen model work.

## 2. Problem Statement

The Gujarat Sentinel challenge requires a practical platform that can ingest heterogeneous government CCTV/VMS sources, maintain a central camera/GIS registry, locate designated vehicles across cameras, preserve timestamps and location-wise history, and demonstrate a working operator workflow. The official source audit is in [`OFFICIAL_REQUIREMENTS_MATRIX.md`](OFFICIAL_REQUIREMENTS_MATRIX.md).

## 3. Proposed Solution

SentinelTrack combines registry-first ingestion, per-camera tracking, ANPR, watchlist matching, conservative appearance support, chronological feasibility analysis, secure APIs, and a control-room dashboard. Existing departmental VMS remains authoritative for continuous recordings; SentinelTrack centralizes permitted metadata, events, alerts, audit, and selected evidence.

## 4. System Architecture

The selected architecture is hybrid: department/regional gateways and inference shards sit near the camera networks, while a central control plane provides catalogue, governance, cross-region search, reporting, API, and audit. The detailed design is [`HLD.md`](HLD.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md). Seven canonical Mermaid diagrams are under [`diagrams/`](diagrams/).

## 5. Functional Capabilities

- camera catalogue and stream health;
- vehicle detection and per-camera ByteTrack tracking;
- plate detection, OCR normalization, and five-frame consensus;
- watchlist registration, matching, alert safeguards, and acknowledgement;
- chronological cross-camera sightings and feasibility explanation;
- masked, track-level, review-only appearance fallback;
- secured API/WebSocket delivery, audit, evidence references, and exportable reports.

## 6. AI/ML Stack

The authoritative model register is [`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md). The frozen stack is YOLO11m vehicle detection, per-camera ByteTrack, selected P11.5 YOLO11s plate detection, PP-OCRv5 Mobile ONNX, five-frame OCR voting, P5 target matching, P7 feasibility, and one MobileNetV3-Small ImageNet appearance baseline for P6.

## 7. Identity Resolution Logic

Strong/full plate evidence dominates. Partial/degraded plates may receive appearance, time, and feasibility support. No usable plate produces appearance-only `REVIEW`/`POSSIBLE` evidence. Plate regions are masked before embedding, and OCR text is never sent to the appearance model. ReID cannot override strong ANPR or create an automatic high/critical identity alert. See [`diagrams/G_identity_fusion.mmd`](diagrams/G_identity_fusion.mmd).

## 8. Accuracy / Evaluation

Authoritative values are classified in [`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md). Selected plate detection reports F1 `0.975610` and mAP50-95 `0.783111`; the plate recognition chain reports TP 143, FP 4, FN 0, F1 `0.986207`, OCR exact 49/143 = `0.3427`, and CER `0.2662`. P1 external vehicle-GT recall/FPR remains unavailable.

P6 has **NO TRUE CROSS-CAMERA VEHICLE-ID GT — THESE ARE APPEARANCE PROXY METRICS ONLY.** The proxy has 240 samples, 61 calibration tracks, 27 locked-test tracks, and no track overlap. Calibration threshold is `0.874001`; locked proxy FMR is `0` and FNMR is `0.459016`.

## 9. Performance

The plate recognition chain measured `33.51 FPS`; this is not complete SentinelTrack end-to-end throughput. PP-OCRv5 Mobile measured P50 `10.53 ms`, P95 `24.85 ms`, and `79.54` crops/s on its locked test. P6 measured 110.65/292.97/391.85 embeddings/s for batch 1/4/8 and gallery P50 1.62/13.61/166.56 ms for 100/1,000/10,000 embeddings. These are local/test measurements, not statewide capacity claims.

## 10. Security

The implemented P10 baseline includes opaque server-side sessions, HttpOnly cookies, Argon2id, CSRF protection, RBAC, authorization, rate limits, WebSocket authorization, session invalidation, and audit paths. OIDC, JWT, Keycloak, HSM, statewide key management, and an independent penetration test are not claimed. See [`SECURITY_PRIVACY.md`](SECURITY_PRIVACY.md).

## 11. GIS / Investigation

P7 provides chronological camera sightings, geodesic/straight-line lower-bound distance, minimum physically required speed, feasibility classification, and same-camera dwell collapse. It does not claim shortest road routes, exact driven paths, live traffic reconstruction, or road-level route snapping.

## 12. Scalability

P11 implements bounded queues, stale-frame dropping, fair scheduling, adaptive base/burst sampling, worker sharding, and health/reset behavior. Existing evidence does not establish safe statewide capacity. The 80k architecture and numbers are explicitly projected from assumptions.

## 13. 80k-Camera Rollout

[`ROLLOUT_80K_CAMERAS.md`](ROLLOUT_80K_CAMERAS.md) models conservative, balanced, and high-efficiency scenarios using total cameras, sampling/burst rates, burst fraction, assumed usable worker capacity, safety margin, headroom, and regional shards. Every node count is `PROJECTED_FROM_ASSUMPTIONS`. The rollout is staged from lab to sandbox, regional pilot, multi-region qualification, and bounded statewide waves.

## 14. Bandwidth / Storage

[`STORAGE_BANDWIDTH_SIZING.md`](STORAGE_BANDWIDTH_SIZING.md) separates raw CCTV traffic, analytics traffic, metadata/events, and selected evidence. At 80,000 cameras, continuous raw traffic at 1/2/4 Mbps is 80/160/320 Gbps, or 864 TB/1.728 PB/3.456 PB per day under explicit bitrate assumptions. The design therefore prefers regional inference and central event/evidence forwarding over duplicating all raw video.

## 15. HA / DR

[`HA_DR_PLAN.md`](HA_DR_PLAN.md) covers stateless API replicas, multiple workers, camera sharding, heartbeats, restart/reassignment, reconnect and stale-drop behavior, PostGIS primary/standby, backups, evidence object storage, integrity checks, monitoring, and audit. Proposed RPO/RTO values are labeled `PROPOSED_DR_TARGET`; no production failover SLA is claimed.

## 16. Cost-Benefit

[`COST_BENEFIT.md`](COST_BENEFIT.md) provides CAPEX/OPEX variables and benefit KPIs without unsupported rupee quotations. Pilot evidence should compare alert latency, review time, evidence completeness, camera availability, false escalation, and investigation turnaround against the existing process.

## 17. Department Dependencies

[`DEPARTMENT_REQUIREMENTS.md`](DEPARTMENT_REQUIREMENTS.md) assigns inputs and acceptance responsibilities across Police/Control Room, CCTV/VMS, IT/Data Centre, Network, Cybersecurity, GIS, Investigation/Operations, Procurement, and Legal/Privacy/Governance. Exact production schemas, credentials, retention, and legal policies require owner confirmation.

## 18. Deployment Plan

[`PILOT_ROADMAP.md`](PILOT_ROADMAP.md) defines lab, sandbox, department, regional, multi-region, and statewide-wave gates. Each stage has infrastructure, measured exit evidence, operational acceptance, risks, and rollback criteria. No stage is represented as already tested at statewide scale.

## 19. Demo Procedure

[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) supplies deterministic fixture, native, container, and official-feed procedures. [`DEMO_SCRIPT_5_MIN.md`](DEMO_SCRIPT_5_MIN.md) gives the timed six-act story: system online, register target, observe, alert, investigate, and explain the ReID fallback. Fixture screens remain visibly labeled `Sample data`.

## 20. Limitations

OCR exact accuracy remains the largest recognition limitation; external P1 vehicle GT is unavailable; P6 lacks true cross-camera labeled identity GT; ReID is intentionally review-only; cloud/multi-node capacity is projected; P7 is not road-level routing; TensorRT is not claimed; and large-scale live Sentinel-network testing has not occurred. Mitigations and non-claims are in [`LIMITATIONS_AND_FUTURE_WORK.md`](LIMITATIONS_AND_FUTURE_WORK.md).

## 21. Future Work

Future enhancements are deliberately outside P12: domain-specific OCR fine-tuning, modern OCR alternatives, vehicle-specific ReID training, a true cross-camera benchmark, TensorRT after validation, larger-gallery ANN search, road-network snapping, distributed infrastructure, larger GPU clusters, and broader real-city evaluation. They are not blockers to this documentation/package freeze.

## 22. Reproducibility / Evidence Index

The exact frozen engineering commit is `1f48aad81a35553ff1e80866a17b1784313efa1b`; the final P12 commit and CI run are recorded in the release handoff. The Conda environment is `PY312` with Python 3.12.12. Model paths and hashes are in [`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md), the claim classifications and source files are in [`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md), and startup/validation commands are in [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) and [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).
