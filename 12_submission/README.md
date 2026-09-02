# SentinelTrack — Priority 12 Submission Package

This directory is the final hackathon-facing package for the SentinelTrack
repository. It explains the frozen implementation, measured evidence,
operator workflow, deployment plan and limits without turning projections into
claims of field performance.

## What SentinelTrack is

SentinelTrack is a production-oriented, multi-camera vehicle intelligence
platform for Gujarat CCTV integration. It combines a camera/GIS registry,
stream ingestion, vehicle detection, per-camera tracking, license-plate
detection and OCR, watchlist matching, a conservative vehicle-appearance
fallback, lower-bound cross-camera trajectory analysis, secure APIs and a
control-room dashboard.

## Official challenge alignment

The official pages describe a compulsory Model 1 registry/GIS foundation plus
one or more interoperable analytics models, a simulated multi-camera test
case, a presentation, an HLD, working-software demonstrations and a statewide
~80,000-camera readiness plan. The source audit and status are in
[`OFFICIAL_REQUIREMENTS_MATRIX.md`](OFFICIAL_REQUIREMENTS_MATRIX.md).

## Package map

| Audience | Start here |
|---|---|
| Evaluator / management | [`FINAL_SUBMISSION_REPORT.md`](FINAL_SUBMISSION_REPORT.md) |
| Technical evaluator | [`HLD.md`](HLD.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md) |
| Camera/GIS/VMS evaluator | [`../docs/CAMERA_REGISTRY_GIS_VMS.md`](../docs/CAMERA_REGISTRY_GIS_VMS.md), [`../reports/model1/MODEL1_GAP_ANALYSIS.md`](../reports/model1/MODEL1_GAP_ANALYSIS.md) |
| Infrastructure evaluator | [`ROLLOUT_80K_CAMERAS.md`](ROLLOUT_80K_CAMERAS.md), [`STORAGE_BANDWIDTH_SIZING.md`](STORAGE_BANDWIDTH_SIZING.md), [`HA_DR_PLAN.md`](HA_DR_PLAN.md) |
| Police/control-room evaluator | [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md), [`DEMO_SCRIPT_5_MIN.md`](DEMO_SCRIPT_5_MIN.md) |
| Governance/security evaluator | [`SECURITY_PRIVACY.md`](SECURITY_PRIVACY.md), [`DEPARTMENT_REQUIREMENTS.md`](DEPARTMENT_REQUIREMENTS.md) |
| Submission owner | [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md), [`PRESENTATION_OUTLINE.md`](PRESENTATION_OUTLINE.md), [`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) |

The complete claim-to-source map is [`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md).
All diagrams are reproducible Mermaid sources under [`diagrams/`](diagrams/).
The current machine-level live-feed diagnosis is documented in the repository
[`LIVE_RUNTIME_AUDIT.md`](../docs/release/LIVE_RUNTIME_AUDIT.md).

## Frozen implementation state

| Phase | State |
|---|---|
| P0 / Model 1 Foundation | DONE; manual/CSV onboarding, GPS provenance, gap exports, and two contract-tested VMS adapter paths |
| P1 Vehicle Detection | DONE; external vehicle GT unavailable |
| P2 Tracking | DONE |
| P3 Plate Detection | DONE; selected P11.5 YOLO11s candidate documented |
| P4 OCR | DONE; measured limitations documented |
| P5 Target Matching | DONE |
| P6 Vehicle ReID Fallback | DONE; review-only proxy evidence |
| P7 Route/GIS | DONE; lower-bound kinematic feasibility, not road routing |
| P8 Backend | DONE |
| P9 Dashboard | DONE |
| P10 Security | DONE |
| P11 Scale/Deployment | DONE |
| P11.5 Optimization/Evidence | FROZEN |
| P12 Submission | THIS PACKAGE |

## Reproducibility

Use the repository's conda environment `PY312` and the exact frozen commit
recorded in the evidence inventory. Model files are external artifacts whose
paths and SHA-256 values are recorded in `models/manifest.json` and the
P11.5/P6 reports. Do not commit credentials or private organizer feeds.

Native runtime commands and the Docker database path are documented in
[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md). The current checkout does not ship a
runtime fixture mode, so all camera status, sightings, alerts, and model
evidence must come from configured services and permitted sources.

## Truth boundary

The package distinguishes measured local/test evidence, simulated fixtures,
assumptions and projections. In particular, no safe 80k-camera capacity has
been measured, P1 vehicle accuracy GT is unavailable, P6 has no true
cross-camera identity GT, and P7 connects observed camera points rather than
roads. These are engineering limits, not hidden claims.

For a real government-feed recording, the organizer-issued feed password,
permitted network access, designated vehicle registration, and any required
department/GIS metadata must be supplied outside the repository. Until those
inputs are available, the application preserves explicit states: missing feed
credentials report `AUTH_REQUIRED`, unavailable hosts report their dependency
failure, and an empty watchlist stays empty instead of producing fabricated
live alerts.

The current 30-camera data snapshot has stream endpoints but no authoritative
GPS/department/organization fields. This is an external metadata gap with an
implemented remediation workflow, not a reason to invent coordinates. The two
VMS connectors are disabled templates until real organization endpoints and
credentials are approved; contract tests are not represented as vendor
acceptance.
