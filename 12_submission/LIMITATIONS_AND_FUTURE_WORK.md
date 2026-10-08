# Limitations and Future Work

These limitations are deliberate boundaries of the frozen hackathon build. They do not invalidate the sandbox demonstration; they define what must be validated before production.

| Limitation | Current truth | Mitigation in submission | Future work class |
|---|---|---|---|
| No true cross-camera vehicle-ID GT | P6 has proxy evidence only | Review-only ReID and explicit evidence labels | `FUTURE_ENHANCEMENT` |
| ReID backbone is generic ImageNet | No vehicle-domain fine-tuning checkpoint | Mask plates, conservative threshold, no automatic high alert | `FUTURE_ENHANCEMENT` |
| Vehicle detector external recall/FPR not authoritative | Dataset/GT is incomplete | Report measured internal artifacts only | `DATA_COLLECTION_REQUIRED` |
| P11 statewide capacity not measured | Available hardware cannot prove 80k | Hierarchical projected model plus staged qualification | `PILOT_REQUIRED` |
| P7 is not road routing | It uses chronological/geodesic lower-bound feasibility | Call it feasibility screening, not route proof | `FUTURE_ENHANCEMENT` |
| Current 30-camera records have no authoritative GPS/ownership fields | Text labels are not survey evidence | Audited edit/CSV workflow plus explicit gap report; never guess coordinates | `EXTERNAL_DATA_REQUIRED` |
| Two VMS adapters lack live departmental acceptance | OGC API Features and ONVIF Profile T are contract tested against deterministic responses | Keep templates disabled until endpoint, secret and owner acceptance are supplied | `PILOT_REQUIRED` |
| Coverage buffers are not measured visibility polygons | No lens, occlusion, terrain or recognition-range survey exists | Label output as a circular-buffer planning approximation | `FUTURE_ENHANCEMENT` |
| Official department schemas/credentials unavailable | Public material does not specify all fields | Requirements matrix and owner questionnaire | `EXTERNAL_DEPENDENCY` |
| Retention, legal hold, and privacy policy are department-specific | No single statewide policy supplied | Data-classification and approval gates | `EXTERNAL_DEPENDENCY` |
| Multi-region HA/DR not game-tested locally | Design and recovery matrix are documented | Pilot game days before production | `PILOT_REQUIRED` |
| Government-feed recording and final portal upload are external | Cannot be completed inside repository | Runbook, scripts, checklist, and output template | `MANUAL_SUBMISSION_ACTION` |
| Exact portal limits/judging weights not publicly verified | Portal-only fields may change | Mark `OFFICIAL_REQUIREMENT_NOT_VERIFIED` | `MANUAL_VERIFICATION_REQUIRED` |

## Non-claims

SentinelTrack does not claim perfect recognition, automatic identity from appearance alone, fabricated camera coordinates, optimal camera placement, live acceptance by unnamed VMS vendors, full 80,000-camera capacity, road-level routing, TensorRT acceleration, an OIDC deployment, or a completed government-feed demonstration until the relevant evidence exists.
