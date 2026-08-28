import pytest
import importlib

_sec = importlib.import_module("10_security")
AuthenticatedPrincipal = _sec.AuthenticatedPrincipal
UserRole = _sec.UserRole
_perms = importlib.import_module("10_security.permissions")
get_permissions_for_role = _perms.get_permissions_for_role
_dep = importlib.import_module("10_security.dependencies")
get_current_principal = _dep.get_current_principal
validate_csrf_token = _dep.validate_csrf_token

backend_app = importlib.import_module("08_backend.app")
app = backend_app.app

DEV_PRINCIPAL = AuthenticatedPrincipal(
    user_id="dev-operator",
    username="operator_p8",
    display_name="P8 Test Operator",
    role=UserRole.ADMIN,
    permissions=get_permissions_for_role(UserRole.ADMIN),
    session_id="dev-session"
)


@pytest.fixture(autouse=True)
def bypass_auth_for_p8_backend_tests():
    """Bypasses auth and CSRF for legacy P8 functional tests using standard FastAPI dependency overrides."""
    app.dependency_overrides[get_current_principal] = lambda: DEV_PRINCIPAL
    app.dependency_overrides[validate_csrf_token] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_principal, None)
    app.dependency_overrides.pop(validate_csrf_token, None)
