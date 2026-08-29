# Video Script and Capture Plan

The official material asks for an own-feed screen recording of approximately 2–3 minutes and a working government-feed demonstration with an output report. Treat these as two separate deliverables.

## Video A — own-feed recording (about 2:30)

| Time | Capture | Voiceover |
|---|---|---|
| 0:00–0:20 | Title and architecture | “SentinelTrack correlates vehicle observations across cameras while preserving source, time, and review provenance.” |
| 0:20–0:55 | Camera catalogue and health | “Cameras are grouped by department and stream epoch. Bounded queues and stale-frame handling protect the live path.” |
| 0:55–1:30 | Vehicle/plate sighting | “The chain detects, tracks, detects the plate, recognizes text, and stores a timestamped sighting.” |
| 1:30–2:00 | Search, timeline, route | “The operator can search, review chronological sightings, and inspect feasibility caveats.” |
| 2:00–2:30 | Alert/audit/export | “Strong ANPR remains authoritative. ReID is a masked, conservative review signal. The report and audit trail preserve what the system actually observed.” |

Show the real running interface and the source label. If fixtures are used, leave `DEMO: ON` visible and say so.

## Video B — government-feed run

Use the organizer-provided government feed and permitted screen capture. Show feed connection, at least one designated-vehicle search, multiple camera sightings with timestamps, the output vehicle/plate report, and any missing/degraded stream state. Avoid recording credentials or restricted imagery outside the permission scope.

## Capture checklist

- 1080p screen capture, readable timestamps, no secrets;
- record the exact commit and environment in the submission manifest;
- keep a copy of the raw recording and final edited version;
- include a text transcript and claims/evidence mapping;
- preserve the generated output report with the same run ID;
- upload using the official permitted unlisted/drive method and test viewer access.

