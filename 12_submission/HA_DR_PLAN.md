# High Availability and Disaster Recovery Plan

Status: **IMPLEMENTED BASELINE PLUS PROPOSED PRODUCTION TARGETS**. The repository contains security, audit, bounded-queue, reset, and deployment building blocks. A multi-region production failover has not been executed locally.

## Service boundaries

| Boundary | Failure isolation | Recovery responsibility |
|---|---|---|
| Camera/VMS gateway | Department or regional | Reconnect, epoch reset, local buffering policy |
| Inference shard | Hash/range of cameras | Scheduler reassigns bounded work to a healthy worker |
| Event/API tier | Region | Stateless replica replacement behind a load balancer |
| PostGIS | Region | Primary/standby, WAL/PITR, tested restore |
| Object storage | Region or approved provider | Versioning/replication and evidence integrity checks |
| State control plane | Central | Configuration, catalogue, identity, audit and reporting |

## Proposed recovery objectives

The following are `PROPOSED_DR_TARGET` values for design review, not measured guarantees:

| Service/data | Proposed RPO | Proposed RTO | Notes |
|---|---:|---:|---|
| Camera health and normalized events | 15 minutes | 60 minutes | Regional store-and-forward may reduce loss |
| Alerts and investigation state | 5 minutes | 30 minutes | Prioritize durable writes and audit trail |
| Evidence object references | 15 minutes | 60 minutes | Object integrity/hash check required |
| Catalogue and configuration | 5 minutes | 30 minutes | Versioned export and protected backup |
| Audit records | 5 minutes | 30 minutes | Append-only export path and reconciliation |

Departments and procurement owners must approve targets before they become SLOs.

## Failure matrix

| Failure | Detection | Degraded behavior | Recovery test |
|---|---|---|---|
| Camera disconnect | Heartbeat/reconnect counters | Mark offline; preserve last-seen truth | Pull cable or stop test stream |
| Gateway loss | Gateway health timeout | Reassign cameras or wait for approved local buffer | Kill gateway process |
| Worker loss | Worker heartbeat/queue lease | Requeue bounded work; avoid duplicate alerting | Stop worker during replay |
| WAN partition | Link and replication lag | Regional inference continues; forward later | Block regional egress |
| API replica loss | Load-balancer health check | Serve from remaining replica | Terminate one replica |
| PostGIS primary loss | Database health/replication monitor | Promote standby if approved | Controlled failover and restore |
| Object-store outage | Write failures/backlog | Keep signed references queued within limit | Deny object writes |
| Full regional loss | Region health and operator escalation | Promote DR region; cameras reconnect by gateway policy | Region-level game day |

## Backup and restore controls

- Use encrypted database backups with point-in-time recovery where supported.
- Version catalogue, model-manifest, configuration, and migration artifacts.
- Store model/checkpoint hashes with deployment manifests; a restored service must not silently load a different model.
- Export audit and evidence manifests separately from mutable UI state.
- Test restore into an isolated environment and reconcile row counts, hashes, event timestamps, stream epochs, and audit continuity.
- Define deletion and legal-hold behavior before enabling replicated evidence storage.

## Integrity and observability

Every recovered event must retain source camera, stream epoch, event time, processing time, model/version, and evidence references. Monitor replication lag, queue age, reconnects, stale drops, duplicate event IDs, missing time windows, failed evidence writes, and alert acknowledgements. A recovery is not complete until the operator can distinguish delayed data from absent data.

