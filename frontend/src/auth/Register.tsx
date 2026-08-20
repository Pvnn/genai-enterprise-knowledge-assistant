import React, { useState } from "react";
import { LockSimple, EnvelopeSimple, BuildingOffice, WarningCircle, ArrowRight } from "@phosphor-icons/react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface RegisterProps {
  onBackToLogin: () => void;
}

export const Register: React.FC<RegisterProps> = ({ onBackToLogin }) => {
  const [activeTab, setActiveTab] = useState<"user" | "enterprise">("user");
  
  // Form state
  const [institution, setInstitution] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!institution.trim() || !email.trim() || !password) {
      setError("All fields are required.");
      return;
    }

    setIsLoading(true);
    setError(null);

    const endpoint = activeTab === "user" ? "/auth/register/user" : "/auth/register/enterprise";
    
    // Map to backend schemas
    const payload = activeTab === "user" 
      ? { tenant_code: institution.trim(), email: email.trim(), password }
      : { enterprise_name: institution.trim(), admin_email: email.trim(), admin_password: password };

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let errorDetail = "Registration failed.";
        try {
          const errData = await response.json();
          errorDetail = errData.detail || errorDetail;
        } catch {
          // ignore
        }
        throw new Error(errorDetail);
      }

      const data = await response.json();
      
      // Store credentials
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("tenant_id", data.tenant_id);
      localStorage.setItem("user_id", data.user_id);
      localStorage.setItem("user_role", data.role);
      
      // Navigate to chat
      window.history.pushState({}, "", "/chat");
      window.dispatchEvent(new PopStateEvent("popstate"));
      
    } catch (err: unknown) {
      setError(err.message || "Network error occurred.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm">

        {/* Brand header */}
        <div className="mb-6 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary-brand mb-4">
            <BuildingsIcon />
          </div>
          <h1 className="text-xl font-bold text-ink tracking-tight">
            Create an Account
          </h1>
          <p className="mt-1 text-xs text-ink-muted">
            Join a team or register a new one
          </p>
        </div>

        {/* Card */}
        <div className="bg-surface rounded-2xl border border-hairline shadow-sm p-6">
          
          {/* Tabs */}
          <div className="flex w-full bg-canvas border border-hairline rounded-lg p-1 mb-6">
            <button
              onClick={() => { setActiveTab("user"); setError(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                activeTab === "user" 
                  ? "bg-surface text-ink shadow-sm border border-hairline" 
                  : "text-ink-muted hover:text-ink border border-transparent"
              }`}
            >
              Join Institution
            </button>
            <button
              onClick={() => { setActiveTab("enterprise"); setError(null); }}
              className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                activeTab === "enterprise" 
                  ? "bg-surface text-ink shadow-sm border border-hairline" 
                  : "text-ink-muted hover:text-ink border border-transparent"
              }`}
            >
              Register Institution
            </button>
          </div>

          {/* Error banner */}
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 px-3 py-2.5">
              <WarningCircle size={16} className="text-red-500 mt-0.5 shrink-0" weight="fill" />
              <p className="text-xs text-red-600 dark:text-red-400 leading-snug">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {/* Institution field */}
            <div>
              <label htmlFor="institution" className="block text-xs font-medium text-ink-muted mb-1.5">
                Institution Name
              </label>
              <div className="relative">
                <BuildingOffice
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
                />
                <input
                  id="institution"
                  type="text"
                  placeholder={activeTab === "user" ? "e.g. Acme University" : "New Institution Name"}
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  disabled={isLoading}
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-hairline bg-canvas text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-brand)] focus:border-transparent disabled:opacity-50 transition-shadow"
                />
              </div>
              {activeTab === "user" && (
                <p className="text-[10px] text-ink-muted mt-1.5 ml-1">Must match the registered name exactly.</p>
              )}
            </div>

            {/* Email field */}
            <div>
              <label htmlFor="email" className="block text-xs font-medium text-ink-muted mb-1.5">
                {activeTab === "enterprise" ? "Admin Email" : "Email Address"}
              </label>
              <div className="relative">
                <EnvelopeSimple
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
                />
                <input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-hairline bg-canvas text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-brand)] focus:border-transparent disabled:opacity-50 transition-shadow"
                />
              </div>
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-xs font-medium text-ink-muted mb-1.5">
                {activeTab === "enterprise" ? "Admin Password" : "Password"}
              </label>
              <div className="relative">
                <LockSimple
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
                />
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl border border-hairline bg-canvas text-ink placeholder:text-ink-muted/60 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-brand)] focus:border-transparent disabled:opacity-50 transition-shadow"
                />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 mt-2 rounded-xl bg-primary-brand hover:bg-[var(--color-primary-brand-hover)] text-white text-sm font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                  </svg>
                  Registering…
                </>
              ) : (
                <>
                  Sign Up
                  <ArrowRight size={15} weight="bold" />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-ink-muted">
          Already have an account?{" "}
          <button
            onClick={onBackToLogin}
            className="font-medium text-[var(--color-primary-brand)] hover:underline focus:outline-none"
          >
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
};

// Helper SVG icon for the header
const BuildingsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
    <path d="M4 21V9L12 3L20 9V21" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M9 21V12H15V21" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);
