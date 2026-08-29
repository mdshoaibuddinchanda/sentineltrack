# Pilot-to-Scale Roadmap

The roadmap turns the submission architecture into a falsifiable operating program. Every phase has an owner, a measured exit gate, and a rollback path.

| Stage | Scope | Purpose | Infrastructure | Validation gate | Operational acceptance | Risks | Rollback |
|---|---|---|---|---|---|---|---|
| Sandbox | Official-like 50-feed scenario | Demonstrate the complete workflow | One host/API, PostGIS, dashboard, deterministic fixtures | Timestamped vehicle/plate report and six-act demo | Evaluator can repeat the run | Fixture/live-feed confusion | Return to deterministic fixtures |
| Department pilot | 10–20 feeds per department | Validate catalogue, roles, retention and connectivity | Department gateway, small worker shard, approved network path | Feed inventory, access audit, sample evidence | Department owner signs off | Missing credentials or clock drift | Remove department gateway |
| Regional pilot | 500–2,000 feeds | Measure sustainable capacity and failure behavior | Regional gateways, GPU workers, PostGIS standby, evidence store | 24–72h soak, load/failover reports | Operations accepts queue/alert SLOs | Burst overload or storage growth | Drain/reassign shard |
| Multi-region | 5,000–10,000 feeds | Validate DR and cross-region governance | Primary/standby regions, replicated manifests, monitoring | Game-day RPO/RTO and reconciliation | SRE and data owner sign off | Replication lag or policy conflict | Promote previous region |
| Statewide waves | 80,000 feeds in bounded waves | Validate cost, SLOs and operations at each wave | Hierarchical gateways, regional clusters, state control plane | Wave scorecard and acceptance | Governance board admits next wave | Hidden cross-region coupling | Roll back latest wave |

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
