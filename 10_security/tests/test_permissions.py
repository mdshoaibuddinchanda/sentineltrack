import pytest
import importlib

_sec = importlib.import_module("10_security")
UserRole = _sec.UserRole
Permission = _sec.Permission
ROLE_PERMISSIONS = _sec.ROLE_PERMISSIONS
has_permission = _sec.has_permission
AuthenticatedPrincipal = _sec.AuthenticatedPrincipal
_perm_mod = importlib.import_module("10_security.permissions")
get_permissions_for_role = _perm_mod.get_permissions_for_role


def make_principal(role: UserRole) -> AuthenticatedPrincipal:
    perms = get_permissions_for_role(role)
    return AuthenticatedPrincipal(
        user_id="test-user-id",
        username="testuser",
        display_name="Test User",
        role=role,
        permissions=perms,
        session_id="test-session-id"
    )


class TestPermissions:
    def test_admin_has_all_permissions(self):
        admin_perms = get_permissions_for_role(UserRole.ADMIN)
        for p in Permission:
            assert p in admin_perms or p.value in admin_perms

    def test_operator_permissions(self):
        op_perms = get_permissions_for_role(UserRole.OPERATOR)
        # Operator has read access and alert ack
        assert Permission.CAMERA_READ in op_perms or Permission.CAMERA_READ.value in op_perms
        assert Permission.TARGET_READ in op_perms or Permission.TARGET_READ.value in op_perms
        assert Permission.ALERT_READ in op_perms or Permission.ALERT_READ.value in op_perms
        assert Permission.ALERT_ACK in op_perms or Permission.ALERT_ACK.value in op_perms
        assert Permission.ROUTE_READ in op_perms or Permission.ROUTE_READ.value in op_perms
        assert Permission.SIGHTING_READ in op_perms or Permission.SIGHTING_READ.value in op_perms
        # Operator cannot manage users or targets
        assert Permission.USER_CREATE not in op_perms and Permission.USER_CREATE.value not in op_perms
        assert Permission.USER_READ not in op_perms and Permission.USER_READ.value not in op_perms
        assert Permission.TARGET_CREATE not in op_perms and Permission.TARGET_CREATE.value not in op_perms
        assert Permission.TARGET_DISABLE not in op_perms and Permission.TARGET_DISABLE.value not in op_perms
        assert Permission.CAMERA_MANAGE not in op_perms and Permission.CAMERA_MANAGE.value not in op_perms

    def test_auditor_permissions(self):
        aud_perms = get_permissions_for_role(UserRole.AUDITOR)
        assert Permission.AUDIT_READ in aud_perms or Permission.AUDIT_READ.value in aud_perms
        assert Permission.METRICS_READ in aud_perms or Permission.METRICS_READ.value in aud_perms
        # Auditor cannot mutate targets or ack alerts
        assert Permission.TARGET_CREATE not in aud_perms and Permission.TARGET_CREATE.value not in aud_perms
        assert Permission.ALERT_ACK not in aud_perms and Permission.ALERT_ACK.value not in aud_perms
        assert Permission.CAMERA_MANAGE not in aud_perms and Permission.CAMERA_MANAGE.value not in aud_perms

    def test_supervisor_permissions(self):
        sup_perms = get_permissions_for_role(UserRole.SUPERVISOR)
        assert Permission.TARGET_CREATE in sup_perms or Permission.TARGET_CREATE.value in sup_perms
        assert Permission.TARGET_UPDATE in sup_perms or Permission.TARGET_UPDATE.value in sup_perms
        assert Permission.TARGET_DISABLE in sup_perms or Permission.TARGET_DISABLE.value in sup_perms
        assert Permission.CAMERA_MANAGE in sup_perms or Permission.CAMERA_MANAGE.value in sup_perms
        # Supervisor cannot manage users
        assert Permission.USER_CREATE not in sup_perms and Permission.USER_CREATE.value not in sup_perms
        assert Permission.USER_DISABLE not in sup_perms and Permission.USER_DISABLE.value not in sup_perms

    def test_has_permission_helper(self):
        op = make_principal(UserRole.OPERATOR)
        assert has_permission(op, Permission.ALERT_READ) is True
        assert has_permission(op, Permission.USER_CREATE) is False

        admin = make_principal(UserRole.ADMIN)
        assert has_permission(admin, Permission.USER_CREATE) is True
        assert has_permission(admin, "user:create") is True
