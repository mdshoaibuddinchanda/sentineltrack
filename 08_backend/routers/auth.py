import importlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

try:
    from ..schemas.auth import LoginRequest, LoginResponse, MeResponse, CsrfResponse, ChangePasswordRequest, UserSummary
except (ImportError, ValueError):
    sch_m = importlib.import_module("08_backend.schemas.auth")
    LoginRequest, LoginResponse, MeResponse, CsrfResponse, ChangePasswordRequest, UserSummary = (
        sch_m.LoginRequest, sch_m.LoginResponse, sch_m.MeResponse, sch_m.CsrfResponse, sch_m.ChangePasswordRequest, sch_m.UserSummary
    )

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
get_security_config = _sec_m.get_security_config
get_security_repository = _sec_m.get_security_repository
get_session_manager = _sec_m.get_session_manager
get_audit_logger = _sec_m.get_audit_logger
verify_password = _sec_m.verify_password
hash_password = _sec_m.hash_password
PasswordPolicy = _sec_m.PasswordPolicy
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
_dep_m = importlib.import_module("10_security.dependencies")
get_current_principal = _dep_m.get_current_principal
validate_csrf_token = _dep_m.validate_csrf_token
get_login_rate_limiter = importlib.import_module("10_security.rate_limit").get_login_rate_limiter
get_permissions_for_role = importlib.import_module("10_security.permissions").get_permissions_for_role
_csrf_m = importlib.import_module("10_security.csrf")
generate_csrf_token = _csrf_m.generate_csrf_token
hash_csrf_token = _csrf_m.hash_csrf_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Session Security"])



@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    config = Depends(get_security_config),
    repo = Depends(get_security_repository),
    session_manager = Depends(get_session_manager),
    audit = Depends(get_audit_logger),
    limiter = Depends(get_login_rate_limiter)
):
    """
    Authenticates operator credentials, sets HttpOnly session cookie,
    and returns initial per-session CSRF token.
    """
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_ip}:{payload.username.strip().lower()}"

    # 1. Rate Limiting Check
    allowed, retry_after = limiter.is_allowed(rate_limit_key)
    if not allowed:
        audit.log_event(
            action="LOGIN_THROTTLED",
            resource_type="auth",
            outcome="DENIED",
            actor_username=payload.username,
            source_ip=client_ip,
            request_id=request.headers.get("X-Request-ID"),
            details={"retry_after": retry_after}
        )
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please retry in {retry_after} seconds."
        )

    # 2. Look up User
    username_norm = payload.username.strip().lower()
    user = repo.get_user_by_username(username_norm)

    # 3. Constant-time password verification check (generic error response on failure)
    valid_auth = False
    fail_reason = "USER_NOT_FOUND"

    if user:
        if not user.enabled:
            fail_reason = "USER_DISABLED"
        elif verify_password(payload.password, user.password_hash):
            valid_auth = True
        else:
            fail_reason = "INVALID_PASSWORD"

    if not valid_auth:
        limiter.record_failure(rate_limit_key)
        audit.log_event(
            action="LOGIN_FAILURE",
            resource_type="auth",
            outcome="FAILURE",
            actor_username=payload.username,
            source_ip=client_ip,
            request_id=request.headers.get("X-Request-ID"),
            details={"reason": fail_reason}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # 4. Successful Authentication
    limiter.record_success(rate_limit_key)
    user.last_login_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    repo.update_user(user)

    # 5. Create Server-Side Session & Cookie
    user_agent = request.headers.get("User-Agent")
    session, raw_session_token, raw_csrf_token = session_manager.create_session(
        user=user,
        source_ip=client_ip,
        user_agent=user_agent
    )

    response.set_cookie(
        key=config.cookie_name,
        value=raw_session_token,
        httponly=True,
        samesite=config.cookie_samesite,
        secure=config.cookie_secure,
        path=config.cookie_path,
        max_age=config.session_absolute_timeout_seconds
    )

    # 6. Audit Login Success
    principal = AuthenticatedPrincipal(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        permissions=set(),
        session_id=session.session_id,
        must_change_password=user.must_change_password
    )
    audit.log_event(
        action="LOGIN_SUCCESS",
        resource_type="auth",
        outcome="SUCCESS",
        principal=principal,
        source_ip=client_ip,
        request_id=request.headers.get("X-Request-ID")
    )

    permissions = list(get_permissions_for_role(user.role))


    return LoginResponse(
        user=UserSummary(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name,
            role=user.role.value,
            must_change_password=user.must_change_password
        ),
        role=user.role.value,
        permissions=permissions,
        csrf_token=raw_csrf_token,
        message="Authentication successful."
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    _csrf = Depends(validate_csrf_token),
    config = Depends(get_security_config),
    session_manager = Depends(get_session_manager),
    audit = Depends(get_audit_logger)
):
    """Terminates active server-side session and clears authentication cookie (requires CSRF)."""
    session = getattr(request.state, "session", None)
    if session:
        session_manager.revoke_session_by_id(session.session_id)

    response.delete_cookie(
        key=config.cookie_name,
        path=config.cookie_path,
        samesite=config.cookie_samesite
    )

    audit.log_event(
        action="LOGOUT",
        resource_type="auth",
        outcome="SUCCESS",
        principal=principal,
        source_ip=request.client.host if request.client else None,
        request_id=request.headers.get("X-Request-ID")
    )

    return {"message": "Session terminated successfully."}


@router.get("/me", response_model=MeResponse)
async def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal)
):
    """Returns currently authenticated operator identity, role, and permission matrix."""
    return MeResponse(
        user=UserSummary(
            user_id=principal.user_id,
            username=principal.username,
            display_name=principal.display_name,
            role=principal.role.value,
            must_change_password=principal.must_change_password
        ),
        role=principal.role.value,
        permissions=list(principal.permissions)
    )


@router.get("/csrf", response_model=CsrfResponse)
async def get_csrf_token(
    request: Request,
    principal: AuthenticatedPrincipal = Depends(get_current_principal)
):
    """Returns CSRF synchronizer token for the current session."""
    session = getattr(request.state, "session", None)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active session required for CSRF token retrieval."
        )
    
    # Generate a fresh CSRF token for the session and persist its hash
    raw_csrf = generate_csrf_token()
    session.csrf_token_hash = hash_csrf_token(raw_csrf)
    repo = get_security_repository()
    repo.save_session(session)

    return CsrfResponse(csrf_token=raw_csrf)


@router.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    _csrf = Depends(validate_csrf_token),
    config = Depends(get_security_config),
    repo = Depends(get_security_repository),
    session_manager = Depends(get_session_manager),
    audit = Depends(get_audit_logger)
):
    """Allows authenticated user to change their own password, invalidating all active sessions."""
    user = repo.get_user_by_id(principal.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not verify_password(payload.current_password, user.password_hash):
        audit.log_event(
            action="PASSWORD_CHANGE_FAILED",
            resource_type="user",
            outcome="FAILURE",
            principal=principal,
            resource_id=user.user_id,
            request_id=request.headers.get("X-Request-ID"),
            details={"reason": "INCORRECT_CURRENT_PASSWORD"}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect.")

    valid, err_msg = PasswordPolicy.validate(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)
    repo.update_user(user)

    # Invalidate all active sessions for this user across all browsers/devices
    session_manager.revoke_all_user_sessions(user.user_id)

    # Clear current browser session cookie
    response.delete_cookie(
        key=config.cookie_name,
        path=config.cookie_path,
        samesite=config.cookie_samesite
    )

    audit.log_event(
        action="PASSWORD_CHANGED",
        resource_type="user",
        outcome="SUCCESS",
        principal=principal,
        resource_id=user.user_id,
        request_id=request.headers.get("X-Request-ID"),
        fail_closed=True
    )

    return {"message": "Password changed successfully. All sessions invalidated, please log in again."}


