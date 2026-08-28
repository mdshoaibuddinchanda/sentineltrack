# Priority 10 Baseline — Security, Authentication, RBAC & Audit

## Overview

Priority 10 converts SentinelTrack from an open development API to a fully authenticated, role-based access control system with comprehensive audit logging.

## Implementation Baseline

| Baseline Attribute | Value |
|---|---|
| P9D frozen commit | `1a9ce5f4fd8d6d153156d8b0335316b9d7245629` |
| Python environment | `C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe` |
| Session mechanism | Opaque server-side token, HttpOnly cookie `sentinel_session` |
| Password hashing | Argon2id via argon2-cffi |
| CSRF protection | Per-session CSRF token, X-CSRF-Token header |

## Architecture: Session Lifecycle

1. Client POSTs credentials to `POST /api/v1/auth/login`
2. Rate limiter checks IP + username combination (sliding window, 5 attempts default)
3. Password verified via Argon2id
4. 256-bit random session token generated, SHA-256 hashed, stored in DB
5. Per-session CSRF token generated, HMAC hashed, stored alongside session
6. `sentinel_session` cookie set: HttpOnly, SameSite=Strict, Secure (prod)
7. Response body includes `csrf_token` (plaintext, one-time exposure)
8. Each subsequent request: middleware validates cookie -> loads session -> extends idle timeout
9. `POST /api/v1/auth/logout` revokes session record from DB

## Password Policy

- Minimum: 15 characters
- Maximum: 128 characters
- No artificial composition rules
- Argon2id: memory >= 19 MiB, iterations >= 2, parallelism >= 1

## Session Policy

- Idle timeout: 30 minutes (sliding)
- Absolute timeout: 8 hours
- Session token: 256-bit random bytes, URL-safe base64 encoded
