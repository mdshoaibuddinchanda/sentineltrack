# Security Policy

SentinelTrack processes sensitive operational data, including vehicle imagery,
license-plate text, camera locations, timestamps, watchlist decisions, and
operator actions. Please handle reports responsibly.

## Scope

This policy covers the SentinelTrack source code, API, dashboard, deployment
configuration, authentication and authorization paths, audit logging, and
security-sensitive documentation in this repository.

The repository is a hackathon submission and is not a production authorization
for a statewide deployment. Production controls, ownership, retention, legal
basis, and departmental approvals are documented separately in
[`12_submission/SECURITY_PRIVACY.md`](12_submission/SECURITY_PRIVACY.md).

## Supported release

Security fixes are tracked against the latest commit on the default/release
branch. Historical experiment folders under `experiments/archive/` are
preserved for provenance and are not supported runtime components.

## Reporting a vulnerability

Please do not open a public issue for an undisclosed vulnerability. Use the
repository's private GitHub vulnerability-reporting channel:

<https://github.com/mdshoaibuddinchanda/sentineltrack/security/advisories/new>

If that channel is unavailable, contact the repository owner privately through
GitHub and include “SentinelTrack security report” in the subject.

A useful report includes:

- affected commit, component, endpoint, or configuration;
- concise reproduction steps or a proof of concept;
- impact and realistic attack prerequisites;
- logs or screenshots with secrets, tokens, plate text, faces, and raw video removed;
- a safe contact method for follow-up.

Do not upload real CCTV footage, real watchlists, credentials, session cookies,
API keys, or unredacted personal data to an issue, pull request, or report.

## Response expectations

Reports will be acknowledged when practical, triaged for reproducibility and
impact, and coordinated with the reporter before public disclosure where a
fix is required. Please allow time for validation and release preparation.

## Existing baseline

The current repository includes session cookies, Argon2id password hashing,
CSRF protection, RBAC, rate limiting, security headers, WebSocket authorization,
session invalidation, audit logging, data classification, and review-safe
identity provenance. It does not claim OIDC, JWT/Keycloak, HSM-backed key
management, a statewide security assessment, or a completed independent
penetration test.

See [`docs/security/`](docs/security/) for the implementation and deployment
security guidance.
