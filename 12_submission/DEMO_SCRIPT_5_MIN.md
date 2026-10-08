# Five-Minute Demonstration Script

Use only decoded live-feed facts for the official run. If a required source is unavailable, show the dependency status and state the limitation; do not invent detections.

| Time | Screen action | Narration |
|---|---|---|
| 0:00–0:35 | Open dashboard and camera catalogue | “SentinelTrack starts with a central catalogue and department-scoped camera identity. Every observation retains camera, timestamp, and stream epoch.” |
| 0:35–1:20 | Open live camera and sighting | “The pipeline samples bounded work, detects vehicles and plates, tracks per camera, and records evidence. The camera status and decoded-frame count show whether this is a real current observation.” |
| 1:20–2:05 | Search an authorized target | “Plate text is normalized before watchlist matching. The result shows the source image, time, camera, and identity provenance rather than only a score.” |
| 2:05–2:55 | Open sightings/route timeline | “The route view is chronological camera sightings and a geodesic lower-bound feasibility check. It is deliberately not road-level routing.” |
| 2:55–3:45 | Open partial/no-plate case | “When ANPR is partial, appearance can support review. P6 masks the plate region, uses a bounded track embedding, and remains review-only. Strong ANPR cannot be overridden.” |
| 3:45–4:30 | Open alert, acknowledge, show audit | “An operator must review and acknowledge. The audit trail records the action, and a missing feed is shown as missing—not as a negative result.” |
| 4:30–5:00 | Export report / show architecture or health panel | “The output is a timestamped vehicle/plate report with provenance. Capacity and 80,000-camera figures in the submission are staged projections pending qualification, not invented measurements.” |

## Claims to avoid

Do not say “100% accuracy,” “appearance proves identity,” “80,000 cameras are already running,” “road routing,” “government feed” when showing fixtures, or “production HA tested” unless the corresponding evidence is actually on screen.
