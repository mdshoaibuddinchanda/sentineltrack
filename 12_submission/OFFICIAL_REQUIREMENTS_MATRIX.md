# Official Gujarat Sentinel Challenge Requirements Matrix

Sources were checked on 30 August 2026. The primary source is the official
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
| Model 1 CCTV Registry/GIS foundation is compulsory | FAQ Q12–15 | Registry, map, onboarding, health and audit capability | P0 registry; P7 GIS; `ARCHITECTURE.md` | COMPLETE | Demonstrate registry onboarding and map |
| Hybrid/custom architecture is allowed | FAQ Q23–25 | State chosen integration model and rationale | `HLD.md`; `FINAL_SUBMISSION_REPORT.md` | COMPLETE | Explain hybrid registry + federation + analytics design |
| Integrate heterogeneous analog/IP, vendors, VMS and protocols | FAQ Q4, Q9–10, Q24; resource guide | HLD and integration adapters | P0 resolver; RTSP/HLS/WHEP catalogue contract; `HLD.md` | PARTIAL | Validate organizer feed protocol and analog-to-VMS gateways during sandbox |
| Support central/regional/edge deployment | FAQ Q24, Q35 | Deployment and scale plan | `ROLLOUT_80K_CAMERAS.md`; diagrams | COMPLETE | Review projected assumptions with department IT |
| Onboard approximately 50 simulated government feeds | FAQ Q26, Q39–41 | Working test-case run and evidence | P0 catalogue client; demo mode; `DEMO_RUNBOOK.md` | PARTIAL | Run against organizer feed; no government feed is available locally |
| Process designated vehicle across camera locations | FAQ Q27–28 | Timestamped sighting history and trajectory output | P5/P7 route API; dashboard investigation view | PARTIAL | Use designated challenge vehicle during sandbox and save output report |
| Provide complete route and location/time movement history | FAQ Q28 | Output report with timestamps and locations | P7 trajectory/GeoJSON APIs; `HLD.md` | COMPLETE | Export challenge run as evidence |
| Solution presentation in PPT or PDF | FAQ Q29 | Slide deck | `PRESENTATION_OUTLINE.md` | PARTIAL | Generate/export final deck and submit it |
| HLD with diagrams, integration, analytics, scalability and department details | FAQ Q29–30 | Technical proposal/HLD | `HLD.md`, `ARCHITECTURE.md`, diagrams, `DEPARTMENT_REQUIREMENTS.md` | COMPLETE | Export to PDF if portal requires PDF |
| Own-feed demonstration, 2–3 minute screen recording | FAQ Q31 | Actual working-software video | `DEMO_SCRIPT_5_MIN.md`, `VIDEO_SCRIPT.md` | PARTIAL | Record a short local-feed video |
| Government-feed demonstration with onboarding, viewing and analytics | FAQ Q31 | Actual working-software video | Demo stack and runbook | PARTIAL | Record during organizer sandbox/production feed access |
| Government-feed video accompanied by timestamped output report | FAQ Q33 | Video plus report | `DEMO_RUNBOOK.md`; P7 export procedure | PARTIAL | Produce report from the live challenge run |
| Mock-ups/animated concept videos are not accepted | FAQ Q32 | Demonstrate real software | React dashboard, FastAPI, demo fixtures | COMPLETE | Use live or recorded working software only |
| Share via unlisted YouTube or viewer-enabled Drive/OneDrive; optional hosted URL/repository | FAQ Q34 | External share links and credentials | GitHub repository; `SUBMISSION_CHECKLIST.md` | PARTIAL | Upload links and verify access manually |
| State-wide ~80,000-camera plan | FAQ Q35 | Compute, bandwidth, storage, HA/DR, monitoring and rollout plan | `ROLLOUT_80K_CAMERAS.md`, `STORAGE_BANDWIDTH_SIZING.md`, `HA_DR_PLAN.md` | COMPLETE | Replace assumptions with organizer infrastructure facts when supplied |
| Evaluation: test case, presentation, architecture, working platform, analytics output, scale/PoC, completeness | FAQ Q36 | Evidence mapped to every area | `FINAL_SUBMISSION_REPORT.md`; this matrix | COMPLETE | Use checklist before upload |
| Bonus features cannot compensate for mandatory non-compliance | FAQ Q37–38 | Prioritize required evidence | `SUBMISSION_CHECKLIST.md` | COMPLETE | Resolve all PARTIAL items before optional polish |
| Approximately 12 hours from 30+ cameras across five departments | FAQ Q39 | Readiness for provided data | `HLD.md`; `DEMO_RUNBOOK.md` | PARTIAL | Obtain actual catalogue/credentials from organizer |
| Use the official catalogue rather than hard-coded camera URLs | Resource guide | Catalogue onboarding implementation | `GET /api/ingest` documented in `HLD.md` | COMPLETE | Verify endpoint against sandbox |
| Official schedule and submission deadline | Schedule page | Submit before stated deadline | `DEMO_RUNBOOK.md`; `SUBMISSION_CHECKLIST.md` | COMPLETE | Confirm portal countdown and local time before upload |
| Team eligibility/category and any supporting certificate | FAQ Q44–46 | Registration/verification documents | Not inferable from repository | BLOCKED | Team owner must confirm Category 1/2 and provide any required certificate |
| Exact upload size, naming convention, judging weights and portal field schema | Public pages checked | Portal-specific packaging | `OFFICIAL_REQUIREMENT_NOT_VERIFIED` | BLOCKED | Confirm from signed-in portal/helpdesk; do not invent values |

## Submission interpretation

The package is technically complete for the published requirements that can be
verified from public official sources. The actual organizer feed demonstration,
external video links, team eligibility, and any portal-only fields remain
manual actions because they require organizer access or team information.
