import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { AuthUser } from '../types/auth';
import type { UserRole } from '../types/auth';
import {
  login as apiLogin,
  logout as apiLogout,
  getMe,
  fetchCsrfToken,
  AuthenticationError,
} from '../api/auth';

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthContextValue {
  user: AuthUser | null;
  /** True while the initial session check is in progress. */
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Returns true if the current user holds the given permission string. */
  hasPermission: (permission: string) => boolean;
  /** Returns true if the current user's role matches a single role or any role in an array. */
  hasRole: (role: UserRole | UserRole[]) => boolean;
  /** Re-fetches and stores a fresh CSRF token (call after long idle periods). */
  refreshCsrf: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Context creation
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // On mount: attempt to restore session by calling getMe()
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const me = await getMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch (err) {
        if (err instanceof AuthenticationError) {
          // No active session — expected on first load or after logout
          if (!cancelled) setUser(null);
        } else {
          // Network or unexpected error — treat as unauthenticated
          console.warn('[AuthProvider] Session check failed:', err);
          if (!cancelled) setUser(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ------------------------------------------------------------------
  // login(): call API login, then fetch full user profile with permissions
  // ------------------------------------------------------------------
  const login = useCallback(
    async (username: string, password: string): Promise<void> => {
      // apiLogin stores the CSRF token in the module
      await apiLogin(username, password);
      // Fetch full profile (includes permissions array)
      const me = await getMe();
      setUser(me);
    },
    []
  );

  // ------------------------------------------------------------------
  // logout(): call API logout, clear local user state
  // ------------------------------------------------------------------
  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
    }
  }, []);

  // ------------------------------------------------------------------
  // hasPermission()
  // ------------------------------------------------------------------
  const hasPermission = useCallback(
    (permission: string): boolean => {
      return user?.permissions.includes(permission) ?? false;
    },
    [user]
  );

  // ------------------------------------------------------------------
  // hasRole()
  // ------------------------------------------------------------------
  const hasRole = useCallback(
    (role: UserRole | UserRole[]): boolean => {
      if (!user) return false;
      if (Array.isArray(role)) {
        return role.includes(user.role);
      }
      return user.role === role;
    },
    [user]
  );

  // ------------------------------------------------------------------
  // refreshCsrf(): re-fetch a fresh CSRF token (e.g. after idle timeout)
  // ------------------------------------------------------------------
  const refreshCsrf = useCallback(async (): Promise<void> => {
    await fetchCsrfToken();
  }, []);

  // ------------------------------------------------------------------
  // Memoised context value
  // ------------------------------------------------------------------
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      logout,
      hasPermission,
      hasRole,
      refreshCsrf,
    }),
    [user, isLoading, login, logout, hasPermission, hasRole, refreshCsrf]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// useAuth hook
// ---------------------------------------------------------------------------

/**
 * Returns the AuthContext value. Must be used inside an <AuthProvider>.
 * Throws if called outside of the provider tree.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error('useAuth must be used within an <AuthProvider>.');
  }
  return ctx;
}

export default AuthContext;
