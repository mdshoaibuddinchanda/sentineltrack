from typing import Set, Dict, Any
from .models import UserRole, Permission



ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    UserRole.ADMIN: {
        Permission.CAMERA_READ.value,
        Permission.TARGET_READ.value,
        Permission.TARGET_CREATE.value,
        Permission.TARGET_UPDATE.value,
        Permission.TARGET_DISABLE.value,
        Permission.SIGHTING_READ.value,
        Permission.ALERT_READ.value,
        Permission.ALERT_ACK.value,
        Permission.ROUTE_READ.value,
        Permission.SYSTEM_READ.value,
        Permission.METRICS_READ.value,
        Permission.AUDIT_READ.value,
        Permission.USER_READ.value,
        Permission.USER_CREATE.value,
        Permission.USER_UPDATE.value,
        Permission.USER_DISABLE.value,
        Permission.USER_RESET_PASSWORD.value,
    },
    UserRole.SUPERVISOR: {
        Permission.CAMERA_READ.value,
        Permission.TARGET_READ.value,
        Permission.TARGET_CREATE.value,
        Permission.TARGET_UPDATE.value,
        Permission.TARGET_DISABLE.value,
        Permission.SIGHTING_READ.value,
        Permission.ALERT_READ.value,
        Permission.ALERT_ACK.value,
        Permission.ROUTE_READ.value,
        Permission.SYSTEM_READ.value,
        Permission.METRICS_READ.value,
        Permission.AUDIT_READ.value,
    },
    UserRole.OPERATOR: {
        Permission.CAMERA_READ.value,
        Permission.TARGET_READ.value,
        Permission.SIGHTING_READ.value,
        Permission.ALERT_READ.value,
        Permission.ALERT_ACK.value,
        Permission.ROUTE_READ.value,
        Permission.SYSTEM_READ.value,
    },
    UserRole.AUDITOR: {
        Permission.CAMERA_READ.value,
        Permission.TARGET_READ.value,
        Permission.SIGHTING_READ.value,
        Permission.ALERT_READ.value,
        Permission.ROUTE_READ.value,
        Permission.SYSTEM_READ.value,
        Permission.METRICS_READ.value,
        Permission.AUDIT_READ.value,
    },
}


def get_permissions_for_role(role: UserRole | str) -> Set[str]:
    role_enum = UserRole(role) if isinstance(role, str) else role
    return ROLE_PERMISSIONS.get(role_enum, set()).copy()


def has_permission(actor: Any, permission: Permission | str) -> bool:
    perm_val = permission.value if isinstance(permission, Permission) else str(permission)
    if hasattr(actor, "permissions") and isinstance(actor.permissions, (set, list, tuple)):
        return perm_val in actor.permissions
    if hasattr(actor, "role"):
        return perm_val in get_permissions_for_role(actor.role)
    role_perms = get_permissions_for_role(actor)
    return perm_val in role_perms

