# Role-Permission Matrix

| Permission | ADMIN | SUPERVISOR | OPERATOR | AUDITOR |
|---|---|---|---|---|
| camera:read | Y | Y | Y | Y |
| target:read | Y | Y | Y | Y |
| target:create | Y | Y | N | N |
| target:update | Y | Y | N | N |
| target:disable | Y | Y | N | N |
| sighting:read | Y | Y | Y | Y |
| alert:read | Y | Y | Y | Y |
| alert:ack | Y | Y | Y | N |
| route:read | Y | Y | Y | Y |
| system:read | Y | Y | Y | Y |
| metrics:read | Y | Y | N | Y |
| audit:read | Y | N | N | Y |
| user:create | Y | N | N | N |
| user:read | Y | N | N | N |
| user:update | Y | N | N | N |
| user:disable | Y | N | N | N |
| user:reset_password | Y | N | N | N |

## Role Descriptions

- **ADMIN**: Full system access including user management and audit. Reserved for system administrators.
- **SUPERVISOR**: Operational authority. Can create/modify/disable targets but cannot manage users or read audit logs.
- **OPERATOR**: Day-to-day monitoring. Read access plus alert acknowledgement.
- **AUDITOR**: Compliance role. Read access plus audit log access. No write operations.
