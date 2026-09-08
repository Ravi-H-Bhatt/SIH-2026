"use client";

import React, { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login({ email, password });
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const setDemoUser = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0B0F19",
        backgroundImage: "radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.15) 0%, transparent 70%)",
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
        {/* Brand Header */}
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
            Sign in to access document screening & risk engine
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#FCA5A5",
              padding: "12px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "24px",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="officer@border.gov"
              style={{
                width: "100%",
                padding: "12px 16px",
                backgroundColor: "rgba(30, 41, 59, 0.7)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                color: "#F8FAFC",
                fontSize: "14px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#CBD5E1", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: "100%",
                padding: "12px 16px",
                backgroundColor: "rgba(30, 41, 59, 0.7)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                color: "#F8FAFC",
                fontSize: "14px",
                outline: "none",
                boxSizing: "border-box",
              }}
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
              transition: "all 0.2s ease",
            }}
          >
            {loading ? "Authenticating..." : "Sign In to Control Center"}
          </button>
        </form>

        {/* Demo Credentials Helper */}
        <div style={{ marginTop: "32px", paddingTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.08)", textAlign: "center" }}>
          <p style={{ fontSize: "11px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "12px" }}>
            Quick Demo Login
          </p>
          <div style={{ display: "flex", gap: "8px", justifyContent: "center" }}>
            <button
              onClick={() => setDemoUser("admin@border.gov", "admin123")}
              style={{
                padding: "6px 12px",
                fontSize: "12px",
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                color: "#FCA5A5",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              👑 Admin
            </button>
            <button
              onClick={() => setDemoUser("officer@border.gov", "officer123")}
              style={{
                padding: "6px 12px",
                fontSize: "12px",
                backgroundColor: "rgba(59, 130, 246, 0.15)",
                color: "#93C5FD",
                border: "1px solid rgba(59, 130, 246, 0.3)",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              👮 Officer
            </button>
            <button
              onClick={() => setDemoUser("supervisor@border.gov", "supervisor123")}
              style={{
                padding: "6px 12px",
                fontSize: "12px",
                backgroundColor: "rgba(245, 158, 11, 0.15)",
                color: "#FDE68A",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: "6px",
                cursor: "pointer",
              }}
            >
              🎖️ Supervisor
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
