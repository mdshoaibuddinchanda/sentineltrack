# OWASP ASVS 5.0 Security Review — SentinelTrack P10D Final Security Freeze

This document summarizes SentinelTrack’s compliance against key sections of OWASP Application Security Verification Standard (ASVS) 5.0 for Level 2 (Standard Enterprise Applications).

---

## V1: Architecture, Design and Threat Modeling
- **Data Classification**: Clearly partitioned between `PUBLIC` (liveness `/health`), `INTERNAL` (`/ready`, `/cameras`), `SENSITIVE` (PII plates, trajectory routes, user accounts), and `SECRET` (Argon2id hashes, session tokens).
- **Fail-Closed Architecture**: Production environments require PostgreSQL database connectivity; missing persistent stores fail closed with descriptive `RuntimeError`.
- **Compensating Rollback**: User creation mutations trigger compensating rollback if the mandatory audit trail write fails.

## V2: Authentication Verification
- **Password Policy**: Enforces minimum 15 characters, maximum 64 characters (`PasswordPolicy.validate`).
- **Cryptographic Hashing**: Passwords stored using `Argon2id` (memory cost 64MB, 3 iterations, 4 parallelism lanes).
- **Brute-Force Rate Limiting**: Progressive delay and account lockout after 5 consecutive failed login attempts within 5 minutes.
- **Session Revocation on Password Change**: Changing a user password immediately revokes all active sessions across devices and clears the current session cookie.

## V3: Session Management
- **Token Entropy**: 256-bit cryptographically secure pseudorandom session tokens (`secrets.token_urlsafe(32)`).
- **Storage**: Raw session tokens never stored plaintext in the database; SHA-256 token hashes are stored and queried.
- **Cookie Security**: `HttpOnly`, `SameSite=Strict`, `Secure` (enforced in production), `Path=/`.
- **Session Expiration**: Enforces 30-minute idle timeout and 8-hour absolute lifetime.

## V4: Access Control (RBAC)
- **Centralized Enforcement**: FastAPI dependency injection (`require_permission`, `get_current_principal`) guards every route.
- **Granular Permissions**: 15 distinct permissions across 4 functional roles (`ADMIN`, `SUPERVISOR`, `OPERATOR`, `AUDITOR`).
- **Administrative Safeguards**: Active administrator count checks prevent demoting or disabling the last active admin.
- **Negative Testing**: Automated programmatic test matrix validates that unauthorized actions return HTTP 403 Forbidden.

## V5: Input Validation & Sanitization
- **SQL Injection Defense**: 100% parameterized SQL queries via `psycopg2` / `sqlite3` driver parameters.
- **Strict Typing**: Pydantic v2 schemas reject type mismatches and truncate/normalize input strings.
- **Log Injection Defense**: CRLF characters (`\r`, `\n`) are stripped from audit details before persistence.

## V8: Data Protection & Cryptography
- **CSRF Defense**: Double-submit / synchronizer memory pattern; state-modifying requests (`POST`, `PATCH`, `DELETE`) require matching `X-CSRF-Token` header.
- **Privacy Masking**: Presentation mode in frontend allows masking PII vehicle registration numbers (e.g. `GJ01***1234`).
- **Credential Transport**: Passwords and session secrets transmitted over HTTPS in production.

## V13: API & Web Service Verification
- **WebSocket Origin Validation**: Handshakes validated against `SecurityConfig.allowed_origins`; untrusted origins closed with code `4403`.
- **WebSocket Topic Authorization**: Wildcard `*` subscriptions expanded and checked against individual role permissions.
- **Production Information Leakage**: Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) disabled in production.

## V14: Configuration
- **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy: default-src 'self'`.
- **Traceability**: Unique correlation ID (`X-Request-ID` / `X-Correlation-ID`) attached to every request and response.
