# SentinelTrack Data Classification Policy

SentinelTrack defines four distinct tiers of data classification to govern access control, storage, and transmission across the system.

---

## 1. Classification Tiers

| Tier | Sensitivity | Description | Examples | Handling & Protection Requirements |
|---|---|---|---|---|
| **PUBLIC** | Low | Non-sensitive operational metadata that can be exposed without authentication. | Health probe status (`/health`), system version string. | No authentication required. No PII or internal architecture details exposed. |
| **INTERNAL** | Medium | Non-PII system topology and metrics needed by authenticated operators. | Camera locations, stream fps, system readiness (`/ready`), performance counters (`/metrics`). | Requires valid session with `system:read` or `metrics:read` permissions. |
| **SENSITIVE** | High | Personally Identifiable Information (PII) and law-enforcement operational data. | Vehicle license plates, sightings timestamps, trajectory routes, alert incident details, operator usernames, audit records. | Requires RBAC authorization (`alert:read`, `route:read`, `audit:read`). Masking support in frontend presentation mode. Log sanitization to prevent CRLF injection. |
| **SECRET** | Critical | Cryptographic keys, credentials, and session tokens. | Argon2id password hashes, session token secrets, CSRF token secrets, database connection passwords. | Transmitted via `HttpOnly` / `Secure` cookies and encrypted channels (HTTPS/WSS). Never logged in audit trails (automatic redaction). Raw tokens stored as SHA-256 hashes in database. |

---

## 2. Redaction & Privacy Controls

- **Audit Logging Redaction**: The `AuditLogger` automatically redacts sensitive keys (`password`, `current_password`, `new_password`, `session_token`, `token`, `secret`, `authorization`, `cookie`) before persistence.
- **Frontend Presentation Mode**: Operators can toggle the `Masked / Redact` button in the dashboard header to mask license plate strings (e.g. `GJ01***1234`) during demonstrations or external reviews.
- **Log Injection Sanitization**: All user-supplied string attributes logged to the security audit trail undergo newline (`\r`, `\n`) stripping.
