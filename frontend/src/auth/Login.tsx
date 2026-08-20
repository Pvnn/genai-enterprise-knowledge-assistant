/**
 * Login page component.
 * Owner: P6
 *
 * Sends POST /auth/login via the login() helper in api/client.ts,
 * stores access_token / tenant_id / user_role in localStorage (matching
 * the keys read by App.tsx and ChatPage.tsx), then navigates to /chat.
 */

import React, { useState, useEffect } from "react";
import { Eye, EyeSlash, EnvelopeSimple, LockSimple, ArrowRight, WarningCircle } from "@phosphor-icons/react";
import { login } from "../api/client";
import { Register } from "./Register";

// ── Types ──────────────────────────────────────────────────────────────────────

interface FormState {
  email: string;
  password: string;
}

interface LoginProps {
  onNavigateRegister?: () => void;
  onLoginSuccess?: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

const Login: React.FC<LoginProps> = ({ onNavigateRegister, onLoginSuccess }) => {
  const [view, setView] = useState<"login" | "register">("login");
  const [form, setForm] = useState<FormState>({
    email: "",
    password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If the user already has a valid token, skip the login page
  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      window.history.replaceState({}, "", "/chat");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  }, []);

  if (view === "register") {
    return <Register onBackToLogin={() => setView("login")} />;
  }


  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.email.trim() || !form.password) {
      setError("All fields are required.");
      return;
    }

    // Hardcoded test admin credentials for local testing
    if (
      (form.email.trim().toLowerCase() === "admin" ||
        form.email.trim().toLowerCase() === "admin@institution.edu" ||
        form.email.trim().toLowerCase() === "admin@test.com") &&
      form.password === "admin"
    ) {
      localStorage.setItem("access_token", "mock-admin-token-xyz");
      localStorage.setItem("tenant_id", "00000000-0000-0000-0000-000000000001");
      localStorage.setItem("user_id", "00000000-0000-0000-0000-000000000002");
      localStorage.setItem("user_role", "admin");

      window.history.pushState({}, "", "/admin");
      window.dispatchEvent(new PopStateEvent("popstate"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const resp = await login({
        email: form.email.trim(),
        password: form.password,
      });

      // Persist auth state — keys match what App.tsx and ChatPage.tsx read
      localStorage.setItem("access_token", resp.access_token);
      localStorage.setItem("tenant_id", resp.tenant_id);
      localStorage.setItem("user_id", resp.user_id);
      localStorage.setItem("user_role", resp.role);

      // Navigate to chat (App.tsx listens to popstate)
      window.history.pushState({}, "", "/chat");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Login failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">

        {/* Brand header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary-brand mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h1 className="text-xl font-bold text-ink tracking-tight">
            Knowledge Assistant
          </h1>
          <p className="mt-1 text-xs text-ink-muted">
            Sign in to your institution
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface rounded-2xl border border-hairline shadow-sm p-6">

          {/* Error banner */}
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-3 py-2.5">
              <WarningCircle size={16} className="text-red-500 mt-0.5 shrink-0" weight="fill" />
              <p className="text-xs text-red-600 dark:text-red-400 leading-snug">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">

            

            {/* Email field */}
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-ink-muted mb-1.5">
                Email
              </label>
              <div className="relative">
                <EnvelopeSimple
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
                />
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@institution.edu"
                  value={form.email}
                  onChange={handleChange}
                  disabled={loading}
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-hairline bg-canvas text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-brand)] focus:border-transparent disabled:opacity-50 transition-shadow"
                />
              </div>
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-ink-muted mb-1.5">
                Password
              </label>
              <div className="relative">
                <LockSimple
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
                />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={handleChange}
                  disabled={loading}
                  className="w-full pl-9 pr-10 py-2.5 text-sm rounded-xl border border-hairline bg-canvas text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-brand)] focus:border-transparent disabled:opacity-50 transition-shadow"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeSlash size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 mt-2 rounded-xl bg-primary-brand hover:bg-[var(--color-primary-brand-hover)] text-white text-sm font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                  </svg>
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight size={15} weight="bold" />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-ink-muted">
          Don't have an account?{" "}
          <button
            onClick={() => setView("register")}
            className="font-medium text-[var(--color-primary-brand)] hover:underline focus:outline-none"
          >
            Sign up
          </button>
        </p>
      </div>
    </div>
  );
};

export default Login;
