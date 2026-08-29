# Security and Privacy

SentinelTrack handles vehicle imagery, plate text, location, timestamps, watchlist decisions, and operator actions. This package separates controls already present in the repository from controls that require production deployment and departmental approval.

## Implemented baseline

- Opaque server-side session with an HttpOnly `sentinel_session` cookie.
- Argon2id password hashing with repository-enforced minimum memory, iterations, and parallelism parameters.
- CSRF header/token protection for state-changing requests.
- 256-bit session-token generation, session invalidation, rate limits, RBAC, audit logging, and WebSocket authorization paths.
- Role/permission matrix and data-classification documentation in `docs/security/`.
- Model and identity explanations that preserve ANPR provenance and keep appearance-only ReID review-safe.

The implementation does **not** claim OIDC, JWT, Keycloak, hardware HSM, statewide key management, or a completed external penetration test.

## Data classes

| Class | Examples | Minimum handling expectation |
|---|---|---|
| Restricted | Plate text, vehicle images, watchlist and investigation records | Least privilege, encryption in transit/at rest, access audit, approved retention |
| Confidential | Camera catalogue, routes, health, model configuration | Role-based access, controlled export, operational audit |
| Internal | Metrics, run manifests, non-sensitive diagnostics | Authenticated access and change history |
| Public | Documentation and non-sensitive aggregate metrics | Review before release |

## Identity safety

The identity hierarchy is mandatory:

1. Strong/full plate evidence remains authoritative.
2. Partial/degraded plates may receive conservative appearance and temporal support.
3. No usable plate produces a possible/review result only; appearance alone cannot create an automated high/critical police identity alert.

Plate regions are masked before P6 appearance embedding. OCR text is never sent to the embedding model. All identity outputs retain `identity_source` and an explanation string.

## Production controls to approve

- Department-specific data owner, purpose, lawful basis, retention, legal hold, and deletion workflow.
- TLS/mTLS between gateways, regional services, databases, and object stores.
- Secret storage and rotation outside source control.
- Network segmentation, private endpoints, firewall policy, egress controls, and admin jump-host policy.
- OIDC/enterprise identity integration if required by the state deployment.
- Immutable or WORM audit storage where evidence policy requires it.
- Vulnerability management, dependency/SBOM scanning, incident response, and independent security assessment.
- Privacy review for masking, operator access, exports, redaction, and subject-access/deletion obligations.

## Operator safeguards

Operators must see whether a result is `ANPR`, `ANPR_REID_SUPPORT`, or `REID_REVIEW`. The UI and exports should show source timestamps, camera/epoch, evidence quality, route-feasibility caveats, and whether a result is measured or inferred. A missing feed must never be rendered as “no vehicle found.”

