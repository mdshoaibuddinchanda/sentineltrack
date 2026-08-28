# OWASP API Security Top 10 Review — SentinelTrack P10

## API1:2023 — Broken Object Level Authorization
**Status: MITIGATED**
All object-level access is gated by `require_permission()` before service calls.
Parameterized queries prevent IDOR via injection.

## API2:2023 — Broken Authentication
**Status: MITIGATED**
Opaque server-side sessions. Argon2id password hashing. Rate-limited login.
HttpOnly SameSite=Strict cookies. Session expiry enforced server-side.

## API3:2023 — Broken Object Property Level Authorization
**Status: PARTIALLY MITIGATED**
Response models use Pydantic schemas limiting exposed fields.
Mass-assignment risk reduced via explicit schema validation on input.
Remaining: some GET endpoints return all fields from the data model.

## API4:2023 — Unrestricted Resource Consumption
**Status: PARTIALLY MITIGATED**
Login rate limiting implemented. No general request rate limiting yet (P11 scope).

## API5:2023 — Broken Function Level Authorization
**Status: MITIGATED**
`require_permission()` enforces function-level access. RBAC matrix centralized.
Admin-only endpoints verified via permission check (not role check) for flexibility.

## API6:2023 — Unrestricted Access to Sensitive Business Flows
**Status: MITIGATED**
Rate limiting on login. CSRF protection on all state-changing flows.

## API7:2023 — Server Side Request Forgery
**Status: NOT APPLICABLE**
No URL input parameters that trigger server-side HTTP requests.

## API8:2023 — Security Misconfiguration
**Status: MITIGATED**
SecurityHeadersMiddleware applies all recommended headers.
CORS restricted to explicit allowlist. Cookie flags enforced.
Debug/docs endpoints available but /docs is not access-controlled (acceptable for hackathon demo).

## API9:2023 — Improper Inventory Management
**Status: MITIGATED**
Full endpoint inventory documented in p10_endpoint_inventory.md.
All endpoints tagged in FastAPI router definitions.

## API10:2023 — Unsafe Consumption of APIs
**Status: NOT APPLICABLE**
Backend does not consume external third-party APIs.
