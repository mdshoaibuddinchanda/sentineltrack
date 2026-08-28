# Deployment Security Guidelines

## Environment Variables

| Variable | Description | Default | Production Required |
|---|---|---|---|
| SENTINEL_SECRET_KEY | 256-bit secret for CSRF HMAC | dev-secret-change-in-production | **YES** — must be rotated |
| SENTINEL_COOKIE_SECURE | Set Secure flag on cookies | false | **YES** — must be true |
| SENTINEL_COOKIE_DOMAIN | Cookie domain scope | None (current domain) | Recommended |
| SENTINEL_ALLOWED_ORIGINS | Comma-separated CORS origins | http://localhost:5173 | **YES** |
| SENTINEL_ARGON2_MEMORY_KB | Argon2id memory in KiB | 19456 (19 MiB) | Keep >= 19456 |
| SENTINEL_ARGON2_ITERATIONS | Argon2id iterations | 2 | Keep >= 2 |
| SENTINEL_ARGON2_PARALLELISM | Argon2id parallelism | 1 | Tune to CPU cores |
| SENTINEL_SESSION_IDLE_TIMEOUT | Idle session timeout (seconds) | 1800 (30 min) | Adjust per policy |
| SENTINEL_SESSION_ABSOLUTE_TIMEOUT | Absolute session timeout (seconds) | 28800 (8 hours) | Adjust per policy |
| SENTINEL_RATE_LIMIT_MAX_ATTEMPTS | Max login attempts before lockout | 5 | Keep <= 10 |
| SENTINEL_RATE_LIMIT_WINDOW_SECONDS | Rate limit window | 900 (15 min) | Keep >= 300 |
| SENTINEL_SECURITY_USE_SQLITE | Force SQLite for security tables | false | false in production |

## First Run: Admin Provisioning

```bash
python -m 10_security.bootstrap_admin
```

This prompts for username and password interactively. Password is never echoed or logged.

## Security Headers Applied

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src self; script-src self; ...`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production only)
- `Cache-Control: no-store, no-cache, must-revalidate` (auth endpoints only)

## Cookie Security Checklist
- [x] HttpOnly: prevents JavaScript access
- [x] SameSite=Strict: prevents cross-origin submission
- [x] Secure: HTTPS-only (enabled via SENTINEL_COOKIE_SECURE=true in production)
- [x] Scoped to /: session valid for all API paths
