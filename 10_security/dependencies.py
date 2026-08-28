from typing import Optional, Callable
from fastapi import Request, HTTPException, status, Depends

from .models import AuthenticatedPrincipal, Permission, UserRole
from .sessions import SessionManager, get_session_manager
from .config import SecurityConfig, get_security_config
from .csrf import verify_csrf_token
from .audit import get_audit_logger


def get_token_from_request(request: Request, config: SecurityConfig) -> Optional[str]:
    """Extracts raw session token from cookie or Authorization header."""
    # 1. Primary: HttpOnly cookie
    cookie_token = request.cookies.get(config.cookie_name)
    if cookie_token:
        return cookie_token

    # 2. Secondary fallback for automated CLI scripts
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_principal(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    config: SecurityConfig = Depends(get_security_config)
) -> AuthenticatedPrincipal:
    """
    FastAPI dependency that extracts and validates the caller's server-side session.
    Raises HTTP 401 if unauthenticated or session expired.
    """
    raw_token = get_token_from_request(request, config)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    res = session_manager.validate_session(raw_token)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session."
        )

    session, user, principal = res
    request.state.principal = principal
    request.state.session = session
    request.state.user = user
    return principal


async def get_optional_principal(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
    config: SecurityConfig = Depends(get_security_config)
) -> Optional[AuthenticatedPrincipal]:
    """Extracts principal if session is valid; returns None if unauthenticated."""
    raw_token = get_token_from_request(request, config)
    if not raw_token:
        return None
    res = session_manager.validate_session(raw_token)
    if not res:
        return None
    _, _, principal = res
    return principal


def require_permission(permission: Permission | str) -> Callable:
    """
    Dependency factory enforcing granular permission on an endpoint.
    Returns HTTP 401 if unauthenticated; HTTP 403 if unauthorized.
    """
    perm_val = permission.value if isinstance(permission, Permission) else str(permission)

    async def permission_checker(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        request: Request = None
    ) -> AuthenticatedPrincipal:
        if not principal.has_permission(perm_val):
            # Log authorization failure in audit trail
            audit = get_audit_logger()
            audit.log_event(
                action="AUTHORIZATION_DENIED",
                resource_type="endpoint",
                outcome="DENIED",
                principal=principal,
                resource_id=request.url.path if request else None,
                request_id=request.headers.get("X-Request-ID") if request else None,
                source_ip=request.client.host if request and request.client else None,
                details={"required_permission": perm_val, "user_role": principal.role.value}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: missing required permission '{perm_val}'."
            )
        return principal

    return permission_checker


def require_role(role: UserRole | str) -> Callable:
    """Dependency factory enforcing specific role membership."""
    role_val = role.value if isinstance(role, UserRole) else str(role)

    async def role_checker(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
        request: Request = None
    ) -> AuthenticatedPrincipal:
        if principal.role.value != role_val:
            audit = get_audit_logger()
            audit.log_event(
                action="AUTHORIZATION_DENIED",
                resource_type="endpoint",
                outcome="DENIED",
                principal=principal,
                resource_id=request.url.path if request else None,
                request_id=request.headers.get("X-Request-ID") if request else None,
                source_ip=request.client.host if request and request.client else None,
                details={"required_role": role_val, "user_role": principal.role.value}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: requires '{role_val}' role."
            )
        return principal

    return role_checker


async def validate_csrf_token(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal)
) -> None:
    """
    Validates per-session synchronizer CSRF token on state-changing requests.
    Exempts GET, HEAD, OPTIONS.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    session = getattr(request.state, "session", None)
    if not session or not session.csrf_token_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not support CSRF verification."
        )

    submitted_csrf = request.headers.get("X-CSRF-Token")
    if not submitted_csrf or not verify_csrf_token(submitted_csrf, session.csrf_token_hash):
        audit = get_audit_logger()
        audit.log_event(
            action="CSRF_VALIDATION_FAILED",
            resource_type="request",
            outcome="DENIED",
            principal=principal,
            resource_id=request.url.path,
            request_id=request.headers.get("X-Request-ID"),
            source_ip=request.client.host if request.client else None,
            details={"method": request.method}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token."
        )

