import uuid
import importlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

try:
    from ..schemas.users import (
        UserCreateRequest, UserUpdateRequest, UserResetPasswordRequest,
        UserResponse, UserListResponse
    )
except (ImportError, ValueError):
    sch_m = importlib.import_module("08_backend.schemas.users")
    UserCreateRequest, UserUpdateRequest, UserResetPasswordRequest, UserResponse, UserListResponse = (
        sch_m.UserCreateRequest, sch_m.UserUpdateRequest, sch_m.UserResetPasswordRequest, sch_m.UserResponse, sch_m.UserListResponse
    )

# 10_security always via importlib (module name starts with digit)
_sec_m = importlib.import_module("10_security")
User = _sec_m.User
UserRole = _sec_m.UserRole
Permission = _sec_m.Permission
get_security_repository = _sec_m.get_security_repository
get_session_manager = _sec_m.get_session_manager
get_audit_logger = _sec_m.get_audit_logger
hash_password = _sec_m.hash_password
PasswordPolicy = _sec_m.PasswordPolicy
AuthenticatedPrincipal = _sec_m.AuthenticatedPrincipal
_dep_m = importlib.import_module("10_security.dependencies")
require_permission = _dep_m.require_permission
validate_csrf_token = _dep_m.validate_csrf_token

router = APIRouter(prefix="/api/v1/users", tags=["User Administration & Identity Management"])



def _user_to_response(u: User) -> UserResponse:
    return UserResponse(
        user_id=u.user_id,
        username=u.username,
        display_name=u.display_name,
        role=u.role.value if isinstance(u.role, UserRole) else str(u.role),
        enabled=u.enabled,
        must_change_password=u.must_change_password,
        created_at=u.created_at,
        updated_at=u.updated_at,
        last_login_at=u.last_login_at
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.USER_READ)),
    repo = Depends(get_security_repository)
):
    """Lists operator accounts in the system (ADMIN only)."""
    users = repo.list_users(limit=limit, offset=offset)
    total = repo.count_users()
    return UserListResponse(
        items=[_user_to_response(u) for u in users],
        total=total
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    payload: UserCreateRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.USER_CREATE)),
    _csrf = Depends(validate_csrf_token),
    repo = Depends(get_security_repository),
    audit = Depends(get_audit_logger)
):
    """Provisions a new operator identity (ADMIN only)."""
    norm_username = payload.username.strip().lower()
    existing = repo.get_user_by_username(norm_username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with username '{norm_username}' already exists."
        )

    valid, err_msg = PasswordPolicy.validate(payload.password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    pwd_hash = hash_password(payload.password)
    now = datetime.now(timezone.utc)
    user = User(
        user_id=str(uuid.uuid4()),
        username=norm_username,
        display_name=payload.display_name.strip(),
        password_hash=pwd_hash,
        role=UserRole(payload.role.value),
        enabled=True,
        must_change_password=payload.must_change_password,
        created_at=now,
        updated_at=now
    )

    try:
        repo.save_user(user)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save user.")

    try:
        audit.log_event(
            action="USER_CREATED",
            resource_type="user",
            outcome="SUCCESS",
            principal=principal,
            resource_id=user.user_id,
            request_id=request.headers.get("X-Request-ID"),
            details={"username": user.username, "role": user.role.value},
            fail_closed=True
        )
    except Exception as audit_exc:
        # Compensate: delete/disable user if audit logging fails
        try:
            repo.disable_user(user.user_id)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security audit trail recording failed; user creation aborted."
        )

    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.USER_READ)),
    repo = Depends(get_security_repository)
):
    """Fetches details for a specific user."""
    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    payload: UserUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.USER_UPDATE)),
    _csrf = Depends(validate_csrf_token),
    repo = Depends(get_security_repository),
    session_manager = Depends(get_session_manager),
    audit = Depends(get_audit_logger)
):
    """Updates user attributes, role, or enabled status (ADMIN only)."""
    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Guard: Prevent disabling or demoting the last active administrator
    if user.role == UserRole.ADMIN or user.role.value == UserRole.ADMIN.value:
        target_role_val = (payload.role.value if hasattr(payload.role, "value") else str(payload.role)) if payload.role is not None else None
        will_demote = target_role_val is not None and target_role_val != UserRole.ADMIN.value
        will_disable = payload.enabled is False
        if will_demote or will_disable:
            active_admins = repo.count_active_admins()
            if active_admins <= 1 and user.enabled:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot disable or demote the last remaining active administrator."
                )


    changes = {}
    if payload.display_name is not None:
        changes["display_name"] = payload.display_name.strip()
        user.display_name = payload.display_name.strip()
    if payload.role is not None:
        changes["role"] = payload.role.value
        user.role = UserRole(payload.role.value)
    if payload.enabled is not None:
        changes["enabled"] = payload.enabled
        user.enabled = payload.enabled
        if not payload.enabled:
            # Revoke all active sessions immediately
            session_manager.revoke_all_user_sessions(user.user_id)
    if payload.must_change_password is not None:
        changes["must_change_password"] = payload.must_change_password
        user.must_change_password = payload.must_change_password

    user.updated_at = datetime.now(timezone.utc)
    repo.update_user(user)

    audit.log_event(
        action="USER_UPDATED",
        resource_type="user",
        outcome="SUCCESS",
        principal=principal,
        resource_id=user.user_id,
        request_id=request.headers.get("X-Request-ID"),
        details=changes,
        fail_closed=True
    )

    return _user_to_response(user)


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    request: Request,
    user_id: str,
    payload: UserResetPasswordRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.USER_RESET_PASSWORD)),
    _csrf = Depends(validate_csrf_token),
    repo = Depends(get_security_repository),
    session_manager = Depends(get_session_manager),
    audit = Depends(get_audit_logger)
):
    """Admin resets a user password and revokes their active sessions."""
    user = repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    valid, err_msg = PasswordPolicy.validate(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = payload.must_change_password
    user.updated_at = datetime.now(timezone.utc)
    repo.update_user(user)

    # Immediately revoke all active sessions for this user
    session_manager.revoke_all_user_sessions(user.user_id)

    audit.log_event(
        action="USER_PASSWORD_RESET",
        resource_type="user",
        outcome="SUCCESS",
        principal=principal,
        resource_id=user.user_id,
        request_id=request.headers.get("X-Request-ID"),
        details={"must_change_password": payload.must_change_password},
        fail_closed=True
    )

    return _user_to_response(user)

