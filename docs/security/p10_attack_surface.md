# SentinelTrack P10 Attack Surface & Threat Model

## 1. Exposed Network Interfaces

### HTTP API Endpoints (`/api/v1`)
| Endpoint | Method | Required Permission | CSRF Protected | Risk Tier | Mitigations |
|---|---|---|---|---|---|
| `/api/v1/auth/login` | POST | None (Public) | No (Login form) | HIGH | Argon2id, IP + username rate limiter, lockout |
| `/api/v1/auth/logout` | POST | Authenticated | **Yes (`X-CSRF-Token`)** | MEDIUM | Session invalidation, cookie clearing |
| `/api/v1/auth/me` | GET | Authenticated | No (Safe read) | LOW | Session lookup, permission reflection |
| `/api/v1/auth/csrf` | GET | Authenticated | No (Safe read) | LOW | Generates fresh CSRF token, persists hash |
| `/api/v1/auth/change-password` | POST | Authenticated | **Yes (`X-CSRF-Token`)** | HIGH | Validates current password, revokes all sessions |
| `/api/v1/users` | GET | `USER_READ` (Admin) | No (Safe read) | MEDIUM | Pagination, role filtering |
| `/api/v1/users` | POST | `USER_CREATE` (Admin) | **Yes (`X-CSRF-Token`)** | HIGH | Audit logging with compensating rollback |
| `/api/v1/users/{id}` | PATCH | `USER_UPDATE` (Admin) | **Yes (`X-CSRF-Token`)** | HIGH | Last admin guard, session revocation on disable |
| `/api/v1/users/{id}/reset-password` | POST | `USER_RESET_PASSWORD` | **Yes (`X-CSRF-Token`)** | HIGH | Revokes all target user sessions |
| `/api/v1/audit` | GET | `AUDIT_READ` (Admin/Auditor) | No (Safe read) | MEDIUM | Sensitive field redaction, pagination |
| `/api/v1/cameras` | GET | `CAMERA_READ` | No (Safe read) | LOW | Parameterized query |
| `/api/v1/targets` | GET | `TARGET_READ` | No (Safe read) | LOW | Parameterized query |
| `/api/v1/targets` | POST | `TARGET_CREATE` | **Yes (`X-CSRF-Token`)** | HIGH | Plate normalization, duplicate check, audit log |
| `/api/v1/targets/{id}` | PATCH | `TARGET_UPDATE` | **Yes (`X-CSRF-Token`)** | HIGH | Audit log |
| `/api/v1/targets/{id}` | DELETE | `TARGET_DISABLE` | **Yes (`X-CSRF-Token`)** | HIGH | Soft delete (is_active=False), audit log |
| `/api/v1/sightings` | GET | `SIGHTING_READ` | No (Safe read) | LOW | Bounded pagination |
| `/api/v1/alerts` | GET | `ALERT_READ` | No (Safe read) | LOW | Bounded pagination |
| `/api/v1/alerts/{id}/ack` | POST | `ALERT_ACK` | **Yes (`X-CSRF-Token`)** | HIGH | Session username binding, audit log |
| `/api/v1/routes/{registration}` | GET | `ROUTE_READ` | No (Safe read) | MEDIUM | Pure read (`persist=False` default) |
| `/health` | GET | None (Public) | No | LOW | Liveness probe (uptime only) |
| `/ready` | GET | `SYSTEM_READ` | No | LOW | Subsystem readiness verification |
| `/metrics` | GET | `METRICS_READ` | No | LOW | Performance & operational metrics |

### WebSocket Endpoint (`/ws/events`)
- **Protocol**: `WSS` / `WS`
- **Handshake Verification**:
  1. `Origin` header validation against `SecurityConfig.allowed_origins` (rejection code `4403`).
  2. `sentinel_session` cookie authentication (rejection code `4401`).
  3. Wildcard `*` and topic authorization (`ALERT_READ`, `SIGHTING_READ`, `CAMERA_READ`, `TARGET_READ`).
- **DoS Mitigation**: Bounded output queue with drop-oldest buffer strategy prevents memory exhaustion from slow clients.
