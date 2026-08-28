-- ==========================================================
-- SentinelTrack Priority 10 Security Schema
-- Users, Sessions, RBAC & Immutable Audit Trail
-- ==========================================================

-- 1. Security Users Table
CREATE TABLE IF NOT EXISTS security_users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_security_users_username
ON security_users(username);

CREATE INDEX IF NOT EXISTS idx_security_users_role_enabled
ON security_users(role, enabled);


-- 2. Server-Side Sessions Table
CREATE TABLE IF NOT EXISTS security_sessions (
    session_id TEXT PRIMARY KEY,
    session_token_hash TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL REFERENCES security_users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    idle_expires_at TIMESTAMPTZ NOT NULL,
    absolute_expires_at TIMESTAMPTZ NOT NULL,
    csrf_token_hash TEXT NOT NULL,
    revoked_at TIMESTAMPTZ,
    source_ip TEXT,
    user_agent_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_security_sessions_token_hash
ON security_sessions(session_token_hash);

CREATE INDEX IF NOT EXISTS idx_security_sessions_user_active
ON security_sessions(user_id, revoked_at);

CREATE INDEX IF NOT EXISTS idx_security_sessions_expires
ON security_sessions(idle_expires_at, absolute_expires_at);


-- 3. Durable Security Audit Trail Table (Append-Only)
CREATE TABLE IF NOT EXISTS security_audit_events (
    audit_id TEXT PRIMARY KEY,
    event_time_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_user_id TEXT,
    actor_username TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    outcome TEXT NOT NULL,
    request_id TEXT,
    source_ip TEXT,
    user_agent TEXT,
    details_json JSONB DEFAULT '{}'::jsonb
);


CREATE INDEX IF NOT EXISTS idx_security_audit_time
ON security_audit_events(event_time_utc DESC);

CREATE INDEX IF NOT EXISTS idx_security_audit_actor
ON security_audit_events(actor_username, event_time_utc DESC);

CREATE INDEX IF NOT EXISTS idx_security_audit_action_resource
ON security_audit_events(action, resource_type, event_time_utc DESC);
