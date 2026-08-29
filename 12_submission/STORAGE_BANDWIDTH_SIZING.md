# Storage and Bandwidth Sizing

Status: **PARAMETERIZED PLANNING MODEL**. The values in this document are assumptions for architecture review, not vendor quotations or measured statewide traffic.

## Raw video ingress reference

For a constant encoded bitrate `B` Mbps and `N` cameras:

`daily_TB = N * B * 86,400 / 8 / 1,000,000`

The table uses decimal TB and assumes the stream is continuously sent at the stated bitrate. Real traffic varies with codec, scene complexity, keyframes, audio, retransmission, and outages.

| Cameras | 1 Mbps | 2 Mbps | 4 Mbps |
|---:|---:|---:|---:|
| 50 | 0.05 Gbps / 0.54 TB/day | 0.10 Gbps / 1.08 TB/day | 0.20 Gbps / 2.16 TB/day |
| 1,000 | 1 Gbps / 10.8 TB/day | 2 Gbps / 21.6 TB/day | 4 Gbps / 43.2 TB/day |
| 10,000 | 10 Gbps / 108 TB/day | 20 Gbps / 216 TB/day | 40 Gbps / 432 TB/day |
| 80,000 | 80 Gbps / 864 TB/day | 160 Gbps / 1.728 PB/day | 320 Gbps / 3.456 PB/day |

These are raw-ingress references. They are not a claim that SentinelTrack should centralize every raw stream. The proposed design terminates or relays video regionally and forwards compact events and selected evidence centrally.

## Metadata and evidence model

An existing repository planning reference uses approximately 75 MB/day for 50 cameras, or a linear planning placeholder of 1.5 MB/camera/day. That reference is `ASSUMPTION` for early sizing only; it is not an audited production payload measurement.

| Scale | Linear metadata placeholder | Monthly placeholder (30 days) |
|---:|---:|---:|
| 50 cameras | 75 MB/day | 2.25 GB |
| 1,000 cameras | 1.5 GB/day | 45 GB |
| 10,000 cameras | 15 GB/day | 450 GB |
| 80,000 cameras | 120 GB/day | 3.6 TB |

Use separate counters for sightings, plate crops, vehicle crops, alert evidence, health telemetry, audit records, and replay manifests. Evidence-image volume should be calculated from the actual event rate:

`evidence_storage = selected_evidence_events * average_bytes_per_event * retention_days`

Do not infer evidence-image volume from raw bitrate.

## Retention tiers

| Tier | Contents | Suggested operational policy |
|---|---|---|
| Hot | Recent alerts, sightings, thumbnails, active investigation data | Fast query; short rolling window; policy-approved |
| Warm | Selected evidence clips/images, normalized events, audit data | Department retention policy and legal hold |
| Cold | Archived evidence and signed export packages | Low-cost storage, retrieval SLA, immutable controls where required |
| Source/VMS | Original raw video | Prefer existing department/VMS retention where contractually and legally appropriate |

Retention durations are intentionally not fixed here. Each department must provide retention, legal-hold, deletion, and evidence-export requirements before production sizing.

## Low-bandwidth behavior

- Keep decode/inference at the gateway or regional worker when possible.
- Send event metadata, hashes, health, and selected evidence rather than duplicating all raw video.
- Apply bounded queues and explicit stale-drop counters during link pressure.
- Compress and batch non-urgent telemetry; preserve alert and audit priority.
- Store-and-forward only within an approved local capacity and retention envelope.
- Surface delay and missing intervals to operators.

## Procurement inputs still required

Actual camera bitrates/codecs, simultaneous stream counts, regional uplinks, retention by department, evidence-event rate, average crop/clip size, database indexes, backup copies, and replication topology must be measured or supplied by the departments. Until then all statewide storage and network totals remain `PROJECTED`.

