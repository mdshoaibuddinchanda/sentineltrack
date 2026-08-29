# Presentation Outline

Status: `SLIDE_CONTENT_COMPLETE`; PPTX generation is a manual submission action unless a local presentation generator is approved and available. The content below is the authoritative slide plan.

## Slide 1 — SentinelTrack

Problem, team, frozen commit, and one-line promise: traceable multi-camera vehicle intelligence with conservative identity safeguards.

## Slide 2 — Official test case

26-department heterogeneous environment, central catalogue/GIS, designated-vehicle history, timestamps, working platform, HLD, and scale readiness. Link to the official requirements matrix.

## Slide 3 — Operator journey

Catalogue → observe → recognize → search → corroborate → review → alert/audit/export. Use a real dashboard screen, not a mockup.

## Slide 4 — End-to-end architecture

Use `diagrams/A_end_to_end_architecture.mmd`. Explain gateway, regional inference, state plane, database/object storage, API, and dashboard.

## Slide 5 — Real-time evidence chain

Use `diagrams/B_realtime_inference_flow.mmd`. Emphasize PTS, stream epoch, bounded queues, track-level aggregation, and provenance.

## Slide 6 — Identity safety

Use `diagrams/G_identity_fusion.mmd`. Strong ANPR wins; partial plates receive support; no-plate ReID is review-only; infeasible travel is suppressed.

## Slide 7 — Measured results

Show only traceable values: plate detector F1 0.975610 on the cited test artifact; OCR P50 10.53 ms/P95 24.85 ms; target matching Recall@100 92.0% and P95 112.55 ms; P6 proxy threshold/FMR/FNMR with the explicit no-cross-camera-GT warning. Trace the slide to [`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md), [`reports/p11_5/end_to_end_evaluation.json`](../reports/p11_5/end_to_end_evaluation.json), and [`reports/p6/P6_EVALUATION.json`](../reports/p6/P6_EVALUATION.json).

## Slide 8 — 80k deployment model

Use `diagrams/D_80k_hierarchical_deployment.mmd`. Present projected scenarios and staged qualification, never measured capacity.

## Slide 9 — HA/DR, security, privacy

Use `diagrams/E_ha_dr.mmd`; cover role controls, audit, recovery, retention, and department approval gates.

## Slide 10 — Demo and output

Show actual dashboard, designated target, timeline, alert, audit, and timestamped report. Explain demo fixture labeling and official-feed deliverable.

## Slide 11 — Pilot and economics

Show the five-stage pilot roadmap, measurable KPIs, parameterized cost model, and procurement inputs.

## Slide 12 — Readiness and ask

State what is frozen and ready for sandbox evaluation, what requires department/organizer action, and the next acceptance gate.
