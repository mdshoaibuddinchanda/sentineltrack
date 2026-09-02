# Official Gujarat Sentinel Challenge Requirements Matrix

Sources were checked on 1 September 2026. The primary source is the official
Gujarat Sentinel website; no unofficial blog is used as a requirement source.

Primary sources:

- FAQ: <https://sentinel.gujarat.gov.in/faqs>
- Problem statement and solution flow: <https://sentinel.gujarat.gov.in/problems>
- Integration guide: <https://sentinel.gujarat.gov.in/resource>
- Schedule: <https://sentinel.gujarat.gov.in/schedule>
- Phases and prizes: <https://sentinel.gujarat.gov.in/phases>

`OFFICIAL_REQUIREMENT_NOT_VERIFIED` means that the public official pages
checked do not state the requested detail. It is not an invitation to guess.

| Requirement | Official source | Required artifact/action | SentinelTrack evidence/location | Status | Final action required |
|---|---|---|---|---|---|
| Model 1 CCTV Registry/GIS foundation is compulsory | FAQ Q12–15 | Registry, map, onboarding, health and audit capability | Manual + bulk onboarding; provenance; gap/GeoJSON exports; P7 GIS; `reports/model1/MODEL1_GAP_ANALYSIS.md` | COMPLETE | Demonstrate one dry-run import, GPS edit, map export and feasibility check |
| Hybrid/custom architecture is allowed | FAQ Q23–25 | State chosen integration model and rationale | `HLD.md`; `FINAL_SUBMISSION_REPORT.md` | COMPLETE | Explain hybrid registry + federation + analytics design |
| Integrate heterogeneous analog/IP, vendors, VMS and protocols | FAQ Q4, Q9–10, Q24; resource guide | HLD and integration adapters | RTSP/HLS/WHEP resolver; contract-tested OGC API Features organization adapter; contract-tested ONVIF Profile T organization/device adapter; `docs/CAMERA_REGISTRY_GIS_VMS.md` | PARTIAL | Supply approved real department endpoints/secrets and record live acceptance; analog sources still enter through their encoder/VMS |
| Support central/regional/edge deployment | FAQ Q24, Q35 | Deployment and scale plan | `ROLLOUT_80K_CAMERAS.md`; diagrams | COMPLETE | Review projected assumptions with department IT |
| Onboard approximately 50 simulated government feeds | FAQ Q26, Q39–41 | Working test-case run and evidence | Dynamic catalogue client; 30 persisted official source definitions; audited manual/CSV/VMS onboarding; `DEMO_RUNBOOK.md` | PARTIAL | Refresh and record the organizer run when its host is available; the feed count is externally controlled and dynamic |
| Process designated vehicle across camera locations | FAQ Q27–28 | Timestamped sighting history and trajectory output | P5/P7 route API; dashboard investigation view | PARTIAL | Use designated challenge vehicle during sandbox and save output report |
| Provide complete route and location/time movement history | FAQ Q28 | Output report with timestamps and locations | P7 trajectory/GeoJSON/CSV; pair feasibility demo; GPS provenance workflow; `HLD.md` | PARTIAL | Import official GPS and export the designated-vehicle challenge run; current names are not silently geocoded |
| Solution presentation in PPT or PDF | FAQ Q29 | Slide deck | `PRESENTATION_OUTLINE.md` | PARTIAL | Generate/export final deck and submit it |
| HLD with diagrams, integration, analytics, scalability and department details | FAQ Q29–30 | Technical proposal/HLD | `HLD.md`, `ARCHITECTURE.md`, diagrams, `DEPARTMENT_REQUIREMENTS.md` | COMPLETE | Export to PDF if portal requires PDF |
| Own-feed demonstration, 2–3 minute screen recording | FAQ Q31 | Actual working-software video | `DEMO_SCRIPT_5_MIN.md`, `VIDEO_SCRIPT.md` | PARTIAL | Record a short local-feed video |
| Government-feed demonstration with onboarding, viewing and analytics | FAQ Q31 | Actual working-software video | Authenticated catalogue, live relay, analytics worker, and runbook | PARTIAL | Record during organizer sandbox/production feed access after password and network authorization |
| Government-feed video accompanied by timestamped output report | FAQ Q33 | Video plus report | Authenticated P7 `/report.csv`; Investigation **Download report**; `DEMO_RUNBOOK.md` | PARTIAL | Download the report from the live challenge run and submit it with the video |
| Mock-ups/animated concept videos are not accepted | FAQ Q32 | Demonstrate real software | React dashboard, FastAPI, live-source status, decoded-frame evidence | COMPLETE | Use live or recorded working software only |
| Share via unlisted YouTube or viewer-enabled Drive/OneDrive; optional hosted URL/repository | FAQ Q34 | External share links and credentials | GitHub repository; `SUBMISSION_CHECKLIST.md` | PARTIAL | Upload links and verify access manually |
| State-wide ~80,000-camera plan | FAQ Q35 | Compute, bandwidth, storage, HA/DR, monitoring and rollout plan | `ROLLOUT_80K_CAMERAS.md`, `STORAGE_BANDWIDTH_SIZING.md`, `HA_DR_PLAN.md` | COMPLETE | Replace assumptions with organizer infrastructure facts when supplied |
| Evaluation: test case, presentation, architecture, working platform, analytics output, scale/PoC, completeness | FAQ Q36 | Evidence mapped to every area | `FINAL_SUBMISSION_REPORT.md`; this matrix | COMPLETE | Use checklist before upload |
| Bonus features cannot compensate for mandatory non-compliance | FAQ Q37–38 | Prioritize required evidence | `SUBMISSION_CHECKLIST.md` | COMPLETE | Resolve all PARTIAL items before optional polish |
| Approximately 12 hours from 30+ cameras across five departments | FAQ Q39 | Readiness for provided data | 30 enabled persisted sources; dynamic onboarding; gap report; `HLD.md`; `DEMO_RUNBOOK.md` | PARTIAL | Obtain authoritative department/GIS metadata and execute the time-bounded organizer test |
| Use the official catalogue rather than hard-coded camera URLs | Resource guide | Catalogue onboarding implementation | Authenticated `GET /cameras.json`, with legacy `/api/ingest` compatibility, documented in `HLD.md` | COMPLETE | Reconfirm the live catalogue immediately before recording |
| Official schedule and submission deadline | Schedule page | Submit before stated deadline | `DEMO_RUNBOOK.md`; `SUBMISSION_CHECKLIST.md` | COMPLETE | Confirm portal countdown and local time before upload |
| Team eligibility/category and any supporting certificate | FAQ Q44–46 | Registration/verification documents | Not inferable from repository | BLOCKED | Team owner must confirm Category 1/2 and provide any required certificate |
| Exact upload size, naming convention, judging weights and portal field schema | Public pages checked | Portal-specific packaging | `OFFICIAL_REQUIREMENT_NOT_VERIFIED` | BLOCKED | Confirm from signed-in portal/helpdesk; do not invent values |

## Submission interpretation

The package is technically complete for the published requirements that can be
verified from public official sources. The actual organizer feed demonstration,
external video links, team eligibility, and any portal-only fields remain
manual actions because they require organizer access or team information.
