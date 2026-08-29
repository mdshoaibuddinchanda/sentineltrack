# Cost and Benefit Model

This is a transparent decision model, not a quotation. Prices, taxes, support contracts, energy, connectivity, cloud region, and procurement rules must be supplied by the selected deployment option.

## Cost variables

`annual_cost = compute + gateway + storage + network + database + observability + security + support + people`

Use separate values for central, regional, and edge tiers. For each tier, record quantity, unit price, support term, power/cooling, and replacement policy. Keep raw-video storage separate from event/evidence storage because the architecture intentionally avoids centralizing every raw stream.

| Cost area | Quantity driver | Evidence state |
|---|---|---|
| GPU/accelerator workers | Measured usable FPS per selected hardware | `PROJECTED; hardware qualification required` |
| CPU decode/gateway | Streams, codec, gateway fan-in | `PROJECTED` |
| Hot/warm/cold storage | Evidence event rate and retention | `PROJECTED_FROM_ASSUMPTIONS` |
| WAN/private connectivity | Regional ingress and metadata egress | `PROJECTED_FROM_BITRATE_ASSUMPTIONS` |
| Database/object store | Events, indexes, replicas, backups | `PROJECTED` |
| Operations | 24x7 coverage, SRE, security, support | `ASSUMPTION` |

## Planning scenarios

These scenarios describe how to build a bill of quantities after qualification. They contain no vendor prices; all quantities are planning assumptions until measured on representative feeds.

| Scenario | Deployment shape | Compute assumption | Storage/network assumption | Decision use |
|---|---|---|---|---|
| Regional-first | Gateways and inference near each department/region | Replace with measured usable FPS/unit | Forward metadata and selected evidence; avoid raw-video duplication | Minimize WAN and central storage |
| Central-control | Regional decode with shared central services | Replace with measured regional worker capacity | Central event store plus approved evidence tiers | Simplify governance and search |
| Hybrid waves | Edge for constrained feeds, regional GPU pools, central control | Qualify each hardware/domain profile | Retain raw video at existing VMS where permitted | Balance resilience, cost, and operations |

For any selected scenario:

`CAPEX = compute + gateway + database/storage + network upgrades + control-room hardware`

`annual OPEX = power/cooling + maintenance + connectivity + storage growth + support + monitoring + people`

## Benefit measures

Benefits should be reported as measurable operational outcomes, not only model scores:

- time from feed observation to operator-visible alert;
- time to locate a designated vehicle across cameras;
- percentage of alerts with complete timestamped evidence;
- analyst review time per incident;
- camera uptime and recovery time;
- false escalation rate and review workload;
- percentage of events with preserved provenance and audit trail.

## Pilot scorecard

Collect a baseline for the existing process, then compare the same test cases with SentinelTrack. Report absolute values, denominator, period, department, and evidence class. Do not monetize safety outcomes without an approved departmental methodology.

## Decision gates

1. Prefer a regional/edge design when raw-video WAN or retention cost dominates.
2. Prefer shared central services when event traffic and governance are manageable and department isolation remains explicit.
3. Procure more compute only after the model/profile and workload are measured on representative streams.
4. Treat false high-severity identity claims as a safety cost; conservative ReID review behavior is an intentional control.
