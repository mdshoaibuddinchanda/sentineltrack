# SentinelTrack — Final Hackathon Submission Report

## 1. Executive summary

SentinelTrack is a hybrid, evidence-preserving platform for multi-camera vehicle observation, plate recognition, target matching, chronological cross-camera correlation, and operator review. The submission package is based on the frozen P6 commit and adds documentation, diagrams, runbooks, and deployment planning; it does not reopen the frozen model work.

## 2. Official problem alignment

The official Gujarat Sentinel material describes heterogeneous government camera sources, a central catalogue/GIS, designated-vehicle tracking across cameras, timestamped/location-wise history, a working platform, presentation/HLD, and a scale-ready deployment plan. The verified source list is in [`OFFICIAL_REQUIREMENTS_MATRIX.md`](OFFICIAL_REQUIREMENTS_MATRIX.md).

## 3. What is implemented

- per-camera vehicle tracking with stream-epoch reset;
- plate detection, OCR normalization, and temporal voting;
- watchlist matching and alert safeguards;
- chronological sightings and lower-bound travel feasibility;
- security/session/RBAC/audit controls documented in the repository;
- P6 masked, track-level, review-only vehicle appearance fallback;
- deterministic dashboard fixtures and container/native demo paths.

The detailed design is [`HLD.md`](HLD.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 4. Model and measured evidence

The authoritative register is [`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md). Key measured artifacts include plate-chain metrics, OCR latency, target-matching benchmark results, and P6 proxy/benchmark values. Each claim is classified in [`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md).

## 5. P6 truth boundary

True cross-camera vehicle identity ground truth was not available locally. P6 therefore reports same-track appearance proxy evidence only: 240 samples, 61 calibration tracks, 27 locked-test tracks, no track overlap; calibration threshold 0.874001; locked proxy false-match rate 0 and false-non-match rate 0.459016. P6 is review-only and cannot create an automatic high/critical identity alert.

## 6. Identity hierarchy

Strong/full plate evidence dominates. Partial/degraded plate evidence may be supported by appearance, time, and feasibility. No usable plate is appearance-only review. Plate regions are masked before embedding. This is explained visually in [`diagrams/G_identity_fusion.mmd`](diagrams/G_identity_fusion.mmd).

## 7. Architecture and deployment

The selected architecture is hybrid: edge/department gateways and regional inference shards, with a central catalogue, event/reporting, and governance plane. The package includes seven canonical Mermaid diagrams and a catalogue/integration contract.

## 8. Scale plan

The 80,000-camera document is a projected staged architecture. No 80,000-camera capacity claim is made. The model uses explicit bitrate, sampling, worker-capacity, margin, and headroom assumptions and requires lab, sandbox, regional, multi-region, and statewide wave gates. See [`ROLLOUT_80K_CAMERAS.md`](ROLLOUT_80K_CAMERAS.md).

## 9. Bandwidth and storage

Raw-video totals are parameterized at 1/2/4 Mbps and show why regional termination and selective central evidence are required. Metadata and evidence sizing are kept separate from raw video. See [`STORAGE_BANDWIDTH_SIZING.md`](STORAGE_BANDWIDTH_SIZING.md).

## 10. HA/DR

The package defines gateway, worker, API, PostGIS, object-store, state-plane, and regional failure boundaries; proposed RPO/RTO targets are clearly not measured. Restore, reconciliation, failover, and game-day tests are required before production. See [`HA_DR_PLAN.md`](HA_DR_PLAN.md).

## 11. Security and privacy

The repository baseline includes opaque sessions, HttpOnly cookies, Argon2id, CSRF protection, RBAC, rate limits, authorization, audit paths, and session invalidation. OIDC, HSM, statewide key management, and independent penetration testing are not claimed. See [`SECURITY_PRIVACY.md`](SECURITY_PRIVACY.md).

## 12. Department and GIS readiness

The department matrix identifies required feed, catalogue, clock, network, role, retention, legal-hold, and acceptance inputs. The public official material does not publish every production schema or credential; those rows are marked `OFFICIAL_REQUIREMENT_NOT_VERIFIED`. See [`DEPARTMENT_REQUIREMENTS.md`](DEPARTMENT_REQUIREMENTS.md).

## 13. Demo

[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md) supplies deterministic, native, container, and official-feed procedures. [`DEMO_SCRIPT_5_MIN.md`](DEMO_SCRIPT_5_MIN.md) is the live narration. Fixtures are visibly labeled and are never represented as government-feed output.

## 14. Submission media

[`VIDEO_SCRIPT.md`](VIDEO_SCRIPT.md) separates the own-feed 2–3 minute recording from the permitted government-feed demonstration and output report. [`PRESENTATION_OUTLINE.md`](PRESENTATION_OUTLINE.md) supplies the slide-by-slide content.

## 15. KPI framework

| KPI | Definition | Evidence class at freeze | Owner for pilot |
|---|---|---|---|
| Feed availability | connected camera minutes / expected camera minutes | `NOT_MEASURED_STATEWIDE` | Department + operations |
| Observation latency | event time to operator-visible event | `MEASURED_LOCAL_IN_PARTS` | Platform |
| Alert latency | qualifying observation to alert creation | `MEASURED_LOCAL_IN_PARTS` | Platform + police |
| Plate exactness | exact recognized plate / evaluated plate cases | `MEASURED_TEST_ON_LOCKED_DATA` | ML/evaluation |
| Review workload | alerts requiring operator review per period | `NOT_MEASURED` | Operations |
| ReID false-match rate | negative proxy pairs above review threshold | `MEASURED_TEST_PROXY_ONLY` | ML/evaluation |
| Evidence completeness | alerts with image, camera, event time, and provenance | `NOT_MEASURED_STATEWIDE` | Platform + departments |
| Recovery | time to restore feed/service after failure | `NOT_MEASURED_PRODUCTION` | SRE |

## 16. Cost/benefit

[`COST_BENEFIT.md`](COST_BENEFIT.md) gives the formulas and procurement inputs. It intentionally avoids unsupported vendor pricing and treats conservative false-escalation avoidance as a safety benefit.

## 17. Reproducibility

The frozen commit, Conda environment, model hashes, source reports, commands, and package inventory are recorded. See [`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md) and [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).

## 18. Limitations

No true cross-camera GT, no statewide capacity measurement, no road-level routing, no universal department schema, and no completed government-feed recording are hidden. See [`LIMITATIONS_AND_FUTURE_WORK.md`](LIMITATIONS_AND_FUTURE_WORK.md).

## 19. Final evaluator message

The platform is a working, safety-bounded sandbox submission with an explicit path to production qualification. Its strongest claim is traceability: an evaluator can follow an observation from feed/camera/epoch through detection, tracking, plate/OCR, target matching, temporal/feasibility support, alert, audit, and exported report.

