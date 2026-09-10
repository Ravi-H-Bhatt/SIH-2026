"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { isSupabaseAuthConfigured } from "@/lib/supabaseClient";

/**
 * Demo quick-fill is a LOCAL DEVELOPMENT convenience and is compiled out unless
 * NEXT_PUBLIC_ENABLE_DEMO_LOGIN === "true". It only prefills the form — it does
 * not bypass authentication, so the backend still verifies the password and the
 * account's approval state. Leave the flag unset on any deployed environment.
 */
const DEMO_LOGIN_ENABLED = process.env.NEXT_PUBLIC_ENABLE_DEMO_LOGIN === "true";

const DEMO_ACCOUNTS = [
  { label: "Admin", email: "admin@border.gov", password: "admin123", tint: "#FCA5A5", bg: "rgba(239,68,68,0.15)", border: "rgba(239,68,68,0.3)" },
  { label: "Supervisor", email: "supervisor@border.gov", password: "supervisor123", tint: "#FDE68A", bg: "rgba(245,158,11,0.15)", border: "rgba(245,158,11,0.3)" },
  { label: "Officer", email: "officer@border.gov", password: "officer123", tint: "#93C5FD", bg: "rgba(59,130,246,0.15)", border: "rgba(59,130,246,0.3)" },
];

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "12px 16px",
  backgroundColor: "rgba(30, 41, 59, 0.7)",
  border: "1px solid rgba(255, 255, 255, 0.1)",
  borderRadius: "8px",
  color: "#F8FAFC",
  fontSize: "14px",
  outline: "none",
  boxSizing: "border-box",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "12px",
  fontWeight: 600,
  color: "#CBD5E1",
  marginBottom: "8px",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleAvailable, setGoogleAvailable] = useState(false);
  const { login, loginWithGoogle, user, isLoading } = useAuth();
  const router = useRouter();

  // Already signed in? Don't show the form again.
  useEffect(() => {
    if (!isLoading && user) router.replace("/");
  }, [isLoading, user, router]);

  // Only offer Google when BOTH sides support it: the browser has Supabase keys
  // and the backend reports the provider as enabled.
  useEffect(() => {
    if (!isSupabaseAuthConfigured) return;
    let alive = true;
    api
      .getAuthProviders()
      .then((p) => alive && setGoogleAvailable(Boolean(p.google)))
      .catch(() => alive && setGoogleAvailable(false));
    return () => {
      alive = false;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ email, password });
      router.replace("/");
    } catch (err: any) {
      setError(err?.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError(null);
    setGoogleLoading(true);
    try {
      await loginWithGoogle();
      // Browser redirects to Google; nothing further runs here.
    } catch (err: any) {
      setError(err?.message || "Google sign-in failed.");
      setGoogleLoading(false);
    }
  };

  const fillDemo = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0B0F19",
        backgroundImage:
          "radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.15) 0%, transparent 70%)",
        padding: "24px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "440px",
          backgroundColor: "rgba(15, 23, 42, 0.85)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "16px",
          padding: "40px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "14px",
              background: "linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "28px",
              margin: "0 auto 16px",
              boxShadow: "0 0 25px rgba(59, 130, 246, 0.4)",
            }}
          >
            🛡️
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 8px" }}>
            Border Guard System
          </h1>
          <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0 }}>
            Authorised personnel only
          </p>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#FCA5A5",
              padding: "12px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "24px",
              lineHeight: 1.5,
            }}
          >
            {error}
          </div>
        )}

        {googleAvailable && (
          <>
            <button
              type="button"
              onClick={handleGoogle}
              disabled={googleLoading}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "8px",
                backgroundColor: "#FFFFFF",
                color: "#1F2937",
                fontWeight: 600,
                fontSize: "14px",
                border: "none",
                cursor: googleLoading ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "10px",
                opacity: googleLoading ? 0.7 : 1,
              }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91a8.78 8.78 0 0 0 2.69-6.62z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86a5.42 5.42 0 0 1-5.09-3.75H.96v2.34A9 9 0 0 0 9 18z" />
                <path fill="#FBBC05" d="M3.91 10.67A5.41 5.41 0 0 1 3.63 9c0-.58.1-1.15.28-1.67V4.99H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.01l2.95-2.34z" />
                <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59A9 9 0 0 0 .96 4.99l2.95 2.34A5.42 5.42 0 0 1 9 3.58z" />
              </svg>
              {googleLoading ? "Redirecting to Google…" : "Continue with Google"}
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "24px 0" }}>
              <span style={{ flex: 1, height: "1px", backgroundColor: "rgba(255,255,255,0.08)" }} />
              <span style={{ fontSize: "11px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                or
              </span>
              <span style={{ flex: 1, height: "1px", backgroundColor: "rgba(255,255,255,0.08)" }} />
            </div>
          </>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "20px" }}>
            <label htmlFor="email" style={labelStyle}>
              Email Address
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@agency.gov.in"
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label htmlFor="password" style={labelStyle}>
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={inputStyle}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "14px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
              color: "#FFF",
              fontWeight: 600,
              fontSize: "15px",
              border: "none",
              cursor: loading ? "not-allowed" : "pointer",
              boxShadow: "0 4px 14px rgba(59, 130, 246, 0.4)",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Authenticating…" : "Sign In"}
          </button>
        </form>

        {DEMO_LOGIN_ENABLED && (
          <div
            style={{
              marginTop: "28px",
              paddingTop: "20px",
              borderTop: "1px solid rgba(255, 255, 255, 0.08)",
              textAlign: "center",
            }}
          >
            <p style={{ fontSize: "11px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "10px" }}>
              Local dev — prefill credentials
            </p>
            <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
              {DEMO_ACCOUNTS.map((acct) => (
                <button
                  key={acct.email}
                  type="button"
                  onClick={() => fillDemo(acct.email, acct.password)}
                  style={{
                    padding: "6px 12px",
                    fontSize: "12px",
                    backgroundColor: acct.bg,
                    color: acct.tint,
                    border: `1px solid ${acct.border}`,
                    borderRadius: "6px",
                    cursor: "pointer",
                  }}
                >
                  {acct.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
