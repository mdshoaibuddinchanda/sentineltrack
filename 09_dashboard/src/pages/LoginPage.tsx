import React, { useId, useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';


export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const errorId = useId();
  const usernameId = useId();
  const passwordId = useId();

  // Redirect immediately if already logged in
  if (!isLoading && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!username.trim()) {
      setErrorMessage('Username is required.');
      return;
    }
    if (!password) {
      setErrorMessage('Password is required.');
      return;
    }

    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Login failed. Please try again.';
      setErrorMessage(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0a0f1a',
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '2.5rem 2rem',
          backgroundColor: '#0f172a',
          border: '1px solid #1e3a5f',
          borderRadius: 12,
          boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
        }}
      >
        {/* Logo / Brand */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 56,
              height: 56,
              borderRadius: '50%',
              backgroundColor: '#1e3a5f',
              marginBottom: '0.75rem',
            }}
          >
            {/* Shield SVG icon */}
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: '1.4rem',
              fontWeight: 700,
              color: '#e2e8f0',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
          >
            SentinelTrack
          </h1>
          <p
            style={{
              margin: '0.25rem 0 0',
              fontSize: '0.78rem',
              color: '#64748b',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
            }}
          >
            Secure Operations Dashboard
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          {/* Username */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label
              htmlFor={usernameId}
              style={{
                display: 'block',
                marginBottom: '0.4rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#94a3b8',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Username
            </label>
            <input
              id={usernameId}
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={submitting}
              aria-describedby={errorMessage ? errorId : undefined}
              aria-invalid={errorMessage ? true : undefined}
              placeholder="Enter your username"
              style={{
                display: 'block',
                width: '100%',
                padding: '0.65rem 0.9rem',
                fontSize: '0.95rem',
                color: '#e2e8f0',
                backgroundColor: '#0d1526',
                border: '1px solid #1e3a5f',
                borderRadius: 6,
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s',
              }}
              onFocus={(e) =>
                (e.currentTarget.style.borderColor = '#38bdf8')
              }
              onBlur={(e) =>
                (e.currentTarget.style.borderColor = '#1e3a5f')
              }
            />
          </div>

          {/* Password */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label
              htmlFor={passwordId}
              style={{
                display: 'block',
                marginBottom: '0.4rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#94a3b8',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Password
            </label>
            <input
              id={passwordId}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              aria-describedby={errorMessage ? errorId : undefined}
              aria-invalid={errorMessage ? true : undefined}
              placeholder="Enter your password"
              style={{
                display: 'block',
                width: '100%',
                padding: '0.65rem 0.9rem',
                fontSize: '0.95rem',
                color: '#e2e8f0',
                backgroundColor: '#0d1526',
                border: '1px solid #1e3a5f',
                borderRadius: 6,
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color 0.15s',
              }}
              onFocus={(e) =>
                (e.currentTarget.style.borderColor = '#38bdf8')
              }
              onBlur={(e) =>
                (e.currentTarget.style.borderColor = '#1e3a5f')
              }
            />
          </div>

          {/* Error Message */}
          {errorMessage && (
            <div
              id={errorId}
              role="alert"
              aria-live="assertive"
              style={{
                marginBottom: '1rem',
                padding: '0.6rem 0.85rem',
                backgroundColor: '#450a0a',
                border: '1px solid #7f1d1d',
                borderRadius: 6,
                fontSize: '0.82rem',
                color: '#fca5a5',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ flexShrink: 0, marginTop: 1 }}
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {errorMessage}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={submitting}
            aria-busy={submitting}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              width: '100%',
              padding: '0.7rem 1rem',
              fontSize: '0.9rem',
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: submitting ? '#64748b' : '#0f172a',
              backgroundColor: submitting ? '#1e3a5f' : '#38bdf8',
              border: 'none',
              borderRadius: 6,
              cursor: submitting ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.15s, color 0.15s',
            }}
          >
            {submitting ? (
              <>
                {/* Inline spinner */}
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  aria-hidden="true"
                  style={{ animation: 'spin 0.75s linear infinite' }}
                >
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Authenticating…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Footer */}
        <p
          style={{
            marginTop: '1.75rem',
            textAlign: 'center',
            fontSize: '0.72rem',
            color: '#334155',
            letterSpacing: '0.04em',
          }}
        >
          RESTRICTED SYSTEM — AUTHORISED PERSONNEL ONLY
        </p>
      </div>

      {/* Keyframe for spinner — injected via style tag */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default LoginPage;
