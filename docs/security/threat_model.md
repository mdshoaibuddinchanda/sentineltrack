# SentinelTrack P10 Threat Model

## System Description
SentinelTrack is a CCTV vehicle intelligence system. The backend is a FastAPI REST/WebSocket API. The frontend is a React dashboard. The system processes sensitive law enforcement data including vehicle registrations, camera locations, and tracking information.

## Trust Boundaries
1. **Browser <-> API**: HTTPS in production, localhost in dev. Mitigated by CORS, CSRF, SameSite cookies.
2. **API <-> Database**: PostgreSQL on private network. No internet exposure.
3. **API <-> CV Workers**: Internal process communication. Worker runs in same process space.

## Threat Catalog

### T1: Credential Stuffing / Brute Force Login
- **Risk**: CRITICAL
- **Mitigation**: `LoginRateLimiter` sliding-window: 5 attempts per 15 minutes per (username, IP). Lockout returns retry-after seconds.

### T2: Session Hijacking (Cookie Theft)
- **Risk**: HIGH
- **Mitigation**: HttpOnly prevents JS access. SameSite=Strict prevents CSRF-based theft. Secure flag in production. Session tokens are 256-bit random (infeasible to guess). Tokens stored as SHA-256 hashes in DB.

### T3: Cross-Site Request Forgery (CSRF)
- **Risk**: HIGH (state-changing endpoints)
- **Mitigation**: Double-submit CSRF pattern. Per-session CSRF token delivered in login response body. All POST/PATCH/DELETE require X-CSRF-Token header matching stored HMAC hash. SameSite=Strict provides defense-in-depth.

### T4: Horizontal Privilege Escalation (IDOR)
- **Risk**: HIGH
- **Mitigation**: `require_permission()` dependency enforces permission before accessing any resource. Parameterized queries prevent injection.

### T5: Vertical Privilege Escalation
- **Risk**: HIGH
- **Mitigation**: RBAC permission matrix enforced server-side. Permissions never derived from client-supplied data. `last_admin_guard` prevents removing the last admin account.

### T6: SQL Injection
- **Risk**: MEDIUM
- **Mitigation**: All DB queries use parameterized statements. No string-concatenated SQL.

### T7: Audit Log Injection / Tampering
- **Risk**: MEDIUM
- **Mitigation**: `sanitize_audit_string()` strips newlines and control characters. Sensitive fields (password, session_token, csrf_token) are redacted via `redact_sensitive_dict()` before logging.

### T8: Cross-Site Scripting (XSS)
- **Risk**: MEDIUM
- **Mitigation**: CSP header restricts script sources. `X-Content-Type-Options: nosniff`. Tokens never in localStorage/sessionStorage. React DOM escapes output by default.

### T9: Information Disclosure via Error Messages
- **Risk**: LOW-MEDIUM
- **Mitigation**: `global_unhandled_exception_handler` returns generic 500 without stack traces. Login always returns same-delay response regardless of failure reason (timing attack mitigation via Argon2id constant-time verify).

### T10: WebSocket Authorization Bypass
- **Risk**: MEDIUM
- **Mitigation**: WS handshake reads `sentinel_session` cookie. Missing/invalid cookie closes with code 4401. Topic-level permission checks enforce `ALERT_READ`, `SIGHTING_READ`, etc. Unauthorized topic subscription closes with 4403.

## Out of Scope (Deferred)
- P6: ReID deferred
- P11: Redis session store for distributed deployment
- P12: Submission packaging
- mTLS between services
- Hardware security module (HSM) for signing keys
