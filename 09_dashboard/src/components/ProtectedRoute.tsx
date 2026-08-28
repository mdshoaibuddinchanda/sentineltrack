import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { UserRole } from '../types/auth';
import { useAuth } from '../context/AuthContext';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ProtectedRouteProps {
  children: React.ReactNode;
  /**
   * If provided, the current user must hold this permission string.
   * Failure renders `fallback` or an Access Denied message — NOT a login redirect.
   */
  requiredPermission?: string;
  /**
   * If provided, the current user's role must match (single role or any in array).
   * Failure renders `fallback` or an Access Denied message — NOT a login redirect.
   */
  requiredRole?: UserRole | UserRole[];
  /**
   * Custom content to render when a permission/role check fails.
   * Defaults to a generic Access Denied panel.
   */
  fallback?: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Loading spinner (reused inline)
// ---------------------------------------------------------------------------

function CenteredLoader() {
  return (
    <div
      role="status"
      aria-label="Loading…"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: 240,
        gap: '0.75rem',
        color: '#64748b',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#38bdf8"
        strokeWidth="2.5"
        strokeLinecap="round"
        aria-hidden="true"
        style={{ animation: 'st-spin 0.75s linear infinite' }}
      >
        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      </svg>
      <span style={{ fontSize: '0.82rem', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        Loading…
      </span>
      <style>{`
        @keyframes st-spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Access Denied panel (default fallback)
// ---------------------------------------------------------------------------

function AccessDenied({ reason }: { reason: string }) {
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: 240,
        gap: '0.75rem',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      <svg
        width="40"
        height="40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#ef4444"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      </svg>
      <p
        style={{
          margin: 0,
          fontSize: '1rem',
          fontWeight: 700,
          color: '#f87171',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        Access Denied
      </p>
      <p
        style={{
          margin: 0,
          fontSize: '0.82rem',
          color: '#64748b',
          textAlign: 'center',
          maxWidth: 320,
        }}
      >
        {reason}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProtectedRoute
// ---------------------------------------------------------------------------

export function ProtectedRoute({
  children,
  requiredPermission,
  requiredRole,
  fallback,
}: ProtectedRouteProps) {
  const { isLoading, isAuthenticated, hasPermission, hasRole } = useAuth();
  const location = useLocation();

  // 1. While auth state is resolving, show spinner
  if (isLoading) {
    return <CenteredLoader />;
  }

  // 2. Not authenticated — redirect to /login, preserving current path
  if (!isAuthenticated) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  // 3. Permission check (does NOT redirect — shows 403-style UI)
  if (requiredPermission !== undefined && !hasPermission(requiredPermission)) {
    return (
      <>
        {fallback ?? (
          <AccessDenied
            reason={`You do not have the required permission: "${requiredPermission}".`}
          />
        )}
      </>
    );
  }

  // 4. Role check (does NOT redirect — shows 403-style UI)
  if (requiredRole !== undefined && !hasRole(requiredRole)) {
    const roleLabel = Array.isArray(requiredRole)
      ? requiredRole.join(', ')
      : requiredRole;
    return (
      <>
        {fallback ?? (
          <AccessDenied
            reason={`This area requires one of the following roles: ${roleLabel}.`}
          />
        )}
      </>
    );
  }

  // 5. All checks passed — render children
  return <>{children}</>;
}

export default ProtectedRoute;
