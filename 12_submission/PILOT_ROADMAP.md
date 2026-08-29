# Pilot-to-Scale Roadmap

The roadmap turns the submission architecture into a falsifiable operating program. Every phase has an owner, a measured exit gate, and a rollback path.

| Stage | Scope | Primary question | Required evidence | Rollback |
|---|---|---|---|---|
| Sandbox | Official-like 50-feed scenario | Does the workflow produce usable timestamped vehicle/plate output? | Demo recording, report, operator sign-off | Return to deterministic fixtures |
| Department pilot | 10–20 feeds per department | Are catalogue, roles, retention and connectivity correct? | Feed inventory, access audit, sample evidence | Remove department gateway |
| Regional pilot | 500–2,000 feeds | What is measured sustainable capacity and failure behavior? | 24–72h soak, load/failover reports | Drain/reassign shard |
| Multi-region | 5,000–10,000 feeds | Does DR preserve identity provenance and audit continuity? | Game-day RTO/RPO and reconciliation | Promote previous region |
| Statewide waves | 80,000 feeds in bounded waves | Do cost, SLOs, and operations scale? | Wave scorecard and acceptance | Roll back latest wave |

## Gate checklist

- stable camera catalogue and stream epochs;
- representative day/night/occlusion samples;
- approved department roles and watchlists;
- observed ingest, inference, OCR, alert, and evidence latencies;
- stale-drop and missing-data reporting;
- retention, deletion, legal-hold, and audit tests;
- worker/gateway failure and database/object-store recovery tests;
- cost per camera/month based on real invoices or procurement estimates;
- operator acceptance that ReID is review support, not proof.

