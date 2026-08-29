# 80,000-Camera Rollout Plan

Status: **PROJECTED ARCHITECTURE AND CAPACITY MODEL — NOT A MEASUREMENT**

SentinelTrack has not measured safe statewide capacity on 80,000 cameras. The frozen P11 evidence proves bounded scheduling, backpressure, stale-frame dropping, fairness, and sharding behavior on the available development hardware; it does not prove a production node count. This document is therefore a deployment model for a staged capacity program, not a capacity claim.

## Design target

The target is a hierarchical deployment in which cameras are owned by regional gateways and workers, while the state control plane receives normalized sightings, alerts, health, audit records, and selected evidence. Raw video remains close to the source unless a retention policy explicitly requires central storage.

```text
camera/VMS -> department gateway -> district shard -> regional control plane -> state control plane
```

The hierarchy limits blast radius, avoids an 80,000-way central fan-in, and allows a district or region to continue operating in degraded mode when the wide-area link is unavailable.

## Evidence boundary

| Item | Status | Meaning |
|---|---|---|
| P11 bounded queues, stale drops, fair scheduling, sharding | `MEASURED_LOCAL` | Implemented and tested in the repository. |
| P6 conditional appearance extraction | `MEASURED_LOCAL` | Benchmarked locally; used only for partial/no-plate tracks and review-safe fallback. |
| 80,000-camera topology | `PROJECTED` | Deployment design to validate in pilots. |
| Worker capacity values below | `ASSUMPTION` | Planning inputs, not measured production capacity. |
| Statewide safe node count | `NOT_MEASURED` | Must be established through load tests and pilot telemetry. |

## Planning model

For a scenario with base sampling rate `b`, burst rate `r`, and burst fraction `q`:

`effective_fps_per_camera = (1 - q) * b + q * r`

For planning only:

`worker_units = ceil(cameras * effective_fps / (usable_fps_per_unit))`

`planned_units = ceil(worker_units / safety_margin) * headroom_factor`

The final result is rounded upward. `usable_fps_per_unit` is a capacity-test input and must be replaced by a measured value for the selected hardware, model profile, resolution, decode path, and concurrency.

| Scenario | Base / burst FPS | Burst fraction | Effective FPS/camera | Assumed usable FPS/unit | Safety margin | Headroom | Planning units for 80k |
|---|---:|---:|---:|---:|---:|---:|---:|
| Conservative | 1 / 5 | 30% | 2.20 | 24 | 60% | 1.25x | 15,279 |
| Balanced | 1 / 5 | 15% | 1.60 | 60 | 70% | 1.20x | 3,658 |
| High-efficiency | 1 / 5 | 10% | 1.40 | 100 | 80% | 1.15x | 1,610 |

These figures are deliberately labeled `PROJECTED_FROM_ASSUMPTIONS`. They must not be presented as “the number of GPUs required” until a hardware qualification test measures the usable rate and failure behavior.

## Capacity qualification gates

1. Reproduce the selected model profile on the intended accelerator and decoder stack.
2. Measure one gateway, one worker, and one regional shard at steady state and burst load.
3. Include reconnects, timestamp gaps, camera epoch resets, OCR queues, database writes, object-store writes, and dashboard subscribers.
4. Measure P50/P95/P99 processing delay, dropped/stale frames, queue age, GPU memory, CPU, decode failures, and alert latency.
5. Repeat with representative camera resolutions, codecs, night scenes, plate visibility, and department-specific streams.
6. Admit a shard only when its measured headroom remains above the agreed safety margin for the full test window.

## Phased rollout

| Phase | Scope | Exit evidence | Rollback |
|---|---|---|---|
| 0: lab | 10–20 replayed feeds | Reproducible metrics and failure injection | Stop replay; preserve traces |
| 1: sandbox | 50–100 official-like feeds | End-to-end route, alert, report, and operator workflow | Disable affected gateway |
| 2: pilot | 500–2,000 cameras across departments | 24–72h soak, measured capacity, retention and DR drill | Drain shard to standby |
| 3: regional | 5,000–10,000 cameras | Multi-region failover and department acceptance | Freeze admission and fail over region |
| 4: statewide | 80,000 cameras in waves | Per-region SLOs, audit, cost, and rollback evidence | Roll back latest wave only |

Each wave is admitted independently. A later wave must not conceal a degraded earlier wave by globally increasing queue limits.

## Runtime safeguards

- Keep camera identity as `(camera_id, stream_epoch)` and reset state after discontinuities.
- Bound every queue; drop stale work before it consumes fresh-frame capacity.
- Prefer metadata and alert continuity over raw-video forwarding during WAN pressure.
- Partition workers by region, department, or camera hash and keep reassignment idempotent.
- Keep the state plane independent from regional inference so health and audit remain visible during inference degradation.
- Mark degraded mode explicitly in operator views; never silently convert missing evidence into a negative finding.

## Acceptance dashboard

The rollout dashboard should expose, per region and department: camera online rate, stream reconnect rate, queue age, stale-drop rate, inference latency, OCR latency, alert latency, evidence write success, GPU/CPU/memory utilization, database replication lag, object-store backlog, and audit-log delivery. The values are operational KPIs to collect; no statewide target is claimed here until the department owners approve SLOs.

