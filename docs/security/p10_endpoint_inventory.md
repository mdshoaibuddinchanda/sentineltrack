# P10 Endpoint Security Inventory

## Authentication Endpoints (Public — No Auth Required)
| Method | Path | Auth | CSRF | Rate Limited | Notes |
|---|---|---|---|---|---|
| POST | /api/v1/auth/login | No | No | Yes (5/15min per user+IP) | Returns session cookie + csrf_token |
| POST | /api/v1/auth/logout | Session | Yes | No | Revokes session |
| GET | /api/v1/auth/me | Session | No | No | Returns current user |
| GET | /api/v1/auth/csrf | Session | No | No | Returns current session CSRF token |
| POST | /api/v1/auth/change-password | Session | Yes | No | Requires current password |

## User Management Endpoints (ADMIN only)
| Method | Path | Permission | CSRF | Audit |
|---|---|---|---|---|
| GET | /api/v1/users | user:read | No | Yes |
| POST | /api/v1/users | user:create | Yes | Yes (fail_closed) |
| GET | /api/v1/users/{id} | user:read | No | No |
| PATCH | /api/v1/users/{id} | user:update | Yes | Yes (fail_closed) |
| POST | /api/v1/users/{id}/reset-password | user:reset_password | Yes | Yes (fail_closed) |

## Audit Endpoints
| Method | Path | Permission | CSRF | Notes |
|---|---|---|---|---|
| GET | /api/v1/audit | audit:read | No | Paginated, filterable |

## Operational Endpoints
| Method | Path | Permission | CSRF | Audit |
|---|---|---|---|---|
| GET | /api/v1/cameras | camera:read | No | No |
| GET | /api/v1/cameras/{id} | camera:read | No | No |
| GET | /api/v1/cameras/nearby | camera:read | No | No |
| GET | /api/v1/cameras/{id}/health | camera:read | No | No |
| GET | /api/v1/cameras/{id}/nearby | camera:read | No | No |
| GET | /api/v1/cameras/{id}/preview | camera:read | No | No |
| GET | /api/v1/cameras/{id}/live | camera:read | No | Continuous MJPEG relay; upstream URL/session never exposed |
| POST | /api/v1/cameras | camera:manage | Yes | Yes (fail_closed) |
| PATCH | /api/v1/cameras/{id}/registry | camera:manage | Yes | Yes (fail_closed) |
| POST | /api/v1/cameras/bulk | camera:manage | Yes | Dry run is non-mutating; apply is fail-closed audited |
| GET | /api/v1/cameras/gap-analysis | camera:read | No | No; current aggregate evidence |
| GET | /api/v1/cameras/gap-analysis.csv | camera:read | No | Yes (`EXPORT_CAMERA_GAP_ANALYSIS`) |
| GET | /api/v1/cameras/export.geojson | camera:read | No | Yes; excludes stream URLs |
| POST | /api/v1/cameras/coverage-analysis | camera:read | Yes | Yes; non-persisting planning estimate |
| GET | /api/v1/cameras/connectors | camera:read | No | No; secret-free readiness only |
| POST | /api/v1/cameras/connectors/{id}/sync | camera:manage | Yes | Validation or fail-closed audited apply |
| GET | /api/v1/targets | target:read | No | No |
| POST | /api/v1/targets | target:create | Yes | Yes (fail_closed) |
| GET | /api/v1/targets/{id} | target:read | No | No |
| PATCH | /api/v1/targets/{id} | target:update | Yes | Yes (fail_closed) |
| DELETE | /api/v1/targets/{id} | target:disable | Yes | Yes (fail_closed) |
| GET | /api/v1/sightings | sighting:read | No | Yes |
| GET | /api/v1/alerts | alert:read | No | No |
| POST | /api/v1/alerts/{id}/acknowledge | alert:ack | Yes | Yes |
| GET | /api/v1/routes/{reg} | route:read | No | Yes |
| GET | /api/v1/routes/{reg}/geojson | route:read | No | Yes |
| GET | /api/v1/routes/{reg}/summary | route:read | No | Yes |
| GET | /api/v1/routes/{reg}/report.csv | route:read | No | Yes (`EXPORT_ROUTE_REPORT`) |
| POST | /api/v1/routes/feasibility-check | route:read | No | Yes; non-persisting lower-bound calculation |

## WebSocket Endpoints
| Path | Auth | Permission Required |
|---|---|---|
| /ws/events | Session cookie | Per-topic: CAMERA_READ, SIGHTING_READ, ALERT_READ, TARGET_READ |
| /ws/alerts | Session cookie | alert:read |
| /ws/sightings | Session cookie | sighting:read |

## Health and telemetry endpoints

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | /health | Public | Liveness and build reference only |
| GET | /ready | system:read | Database, models, and secret-free feed diagnostics |
| GET | /metrics | metrics:read | Operational counters |
| GET | /metrics/prometheus | metrics:read | Prometheus text exposition |
