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

