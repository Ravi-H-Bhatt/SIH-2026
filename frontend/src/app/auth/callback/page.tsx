"use client";

/**
 * Google OAuth return leg.
 *
 * Supabase drops the browser back here with a session. We read that session's
 * access token and POST it to our backend, which verifies it against Supabase
 * server-side and returns an application JWT. The Supabase token itself is never
 * used to call application endpoints.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, USER_STORAGE_KEY } from "@/lib/api";
import { getSupabaseClient } from "@/lib/supabaseClient";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const supabase = getSupabaseClient();
      if (!supabase) {
        setError("Google sign-in is not configured on this deployment.");
        return;
      }

      try {
        // detectSessionInUrl handles both the PKCE code and implicit hash flows.
        const { data, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw new Error(sessionError.message);

        const supabaseToken = data.session?.access_token;
        if (!supabaseToken) {
          throw new Error("Google did not return a session. Please try again.");
        }

        const res = await api.loginWithGoogle(supabaseToken);
        if (cancelled) return;

        localStorage.setItem(
          USER_STORAGE_KEY,
          JSON.stringify({
            id: res.user_id,
            email: res.email,
            full_name: res.full_name,
            role: res.role,
            is_active: true,
            created_at: new Date().toISOString(),
          })
        );

        // Full reload so AuthProvider rehydrates from storage with the new token.
        window.location.replace("/");
      } catch (err: any) {
        if (!cancelled) setError(err?.message || "Google sign-in failed.");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0B0F19",
        padding: "24px",
      }}
    >
      <div
        style={{
          maxWidth: "420px",
          width: "100%",
          textAlign: "center",
          backgroundColor: "rgba(15,23,42,0.85)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "16px",
          padding: "40px",
        }}
      >
        {error ? (
          <>
            <div style={{ fontSize: "32px", marginBottom: "16px" }}>⚠️</div>
            <h1 style={{ fontSize: "18px", color: "#F8FAFC", margin: "0 0 12px" }}>
              Sign-in could not be completed
            </h1>
            <p style={{ fontSize: "13px", color: "#FCA5A5", margin: "0 0 24px", lineHeight: 1.6 }}>
              {error}
            </p>
            <button
              onClick={() => router.replace("/login")}
              style={{
                padding: "10px 20px",
                borderRadius: "8px",
                border: "1px solid rgba(255,255,255,0.15)",
                backgroundColor: "rgba(59,130,246,0.15)",
                color: "#93C5FD",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <div style={{ fontSize: "32px", marginBottom: "16px" }}>🛡️</div>
            <h1 style={{ fontSize: "18px", color: "#F8FAFC", margin: "0 0 8px" }}>
              Verifying your identity
            </h1>
            <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0 }}>
              Completing secure sign-in…
            </p>
          </>
        )}
      </div>
    </div>
  );
}
