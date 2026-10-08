import React, { useId, useState } from "react";
import { AlertCircle, ArrowRight, LoaderCircle, Shield } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const errorId = useId();
  const usernameId = useId();
  const passwordId = useId();

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);

    if (!username.trim()) {
      setErrorMessage("Enter your username.");
      return;
    }
    if (!password) {
      setErrorMessage("Enter your password.");
      return;
    }

    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/", { replace: true });
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Sign in failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <div className="login-mark" aria-hidden="true"><Shield size={28} /></div>
          <p className="login-kicker">Secure operations dashboard</p>
          <h1 id="login-title">Sign in to SentinelTrack</h1>
          <p>Use your authorised operator account to continue.</p>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="login-field">
            <label htmlFor={usernameId}>Username</label>
            <input
              id={usernameId}
              type="text"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={submitting}
              aria-describedby={errorMessage ? errorId : undefined}
              aria-invalid={errorMessage ? true : undefined}
              placeholder="Enter username"
            />
          </div>

          <div className="login-field">
            <label htmlFor={passwordId}>Password</label>
            <input
              id={passwordId}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
              aria-describedby={errorMessage ? errorId : undefined}
              aria-invalid={errorMessage ? true : undefined}
              placeholder="Enter password"
            />
          </div>

          {errorMessage && (
            <div id={errorId} className="login-error" role="alert" aria-live="assertive">
              <AlertCircle size={17} aria-hidden="true" />
              <span>{errorMessage}</span>
            </div>
          )}

          <button type="submit" className="login-submit" disabled={submitting} aria-busy={submitting}>
            {submitting ? <LoaderCircle size={18} className="login-spinner" /> : <ArrowRight size={18} />}
            {submitting ? "Signing in" : "Sign in"}
          </button>
        </form>

        <p className="login-notice">Restricted system. Authorised personnel only.</p>
      </section>
    </main>
  );
}

export default LoginPage;
