"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

const STATS = [
  { value: "99.7%", label: "Detection Accuracy", icon: "🎯" },
  { value: "<3s", label: "Avg. Scan Time", icon: "⚡" },
  { value: "150+", label: "Document Types", icon: "📄" },
  { value: "24/7", label: "Live Monitoring", icon: "🛡️" },
];

const FEATURES = [
  {
    icon: "🔍",
    title: "MRZ & Barcode Verification",
    desc: "ICAO Doc 9303 compliant MRZ parsing with checksum validation across TD1, TD2, TD3 formats.",
    color: "#3B82F6",
  },
  {
    icon: "🤖",
    title: "AI Forgery Detection",
    desc: "Deep learning models detect splicing, cloning, print artifacts, and font inconsistencies.",
    color: "#8B5CF6",
  },
  {
    icon: "👁️",
    title: "Biometric Face Matching",
    desc: "Liveness detection + face morph attack detection against the photo on the document.",
    color: "#EC4899",
  },
  {
    icon: "🌐",
    title: "Sanctions & Watchlist Check",
    desc: "Real-time cross-reference with OpenSanctions, INTERPOL Red Notice, and UN consolidated lists.",
    color: "#10B981",
  },
  {
    icon: "📊",
    title: "Risk Scoring Engine",
    desc: "Multi-factor composite risk score (0–100) with explainable AI reasoning for every scan.",
    color: "#F59E0B",
  },
  {
    icon: "🔗",
    title: "Blockchain Audit Trail",
    desc: "Immutable SHA-256 hash chain ensures tamper-proof evidence with cryptographic integrity.",
    color: "#EF4444",
  },
];

const TECH_STACK = [
  { name: "Next.js 15", category: "Frontend" },
  { name: "FastAPI", category: "Backend" },
  { name: "Supabase", category: "Database" },
  { name: "Python AI/ML", category: "Intelligence" },
  { name: "OpenCV", category: "Vision" },
  { name: "Vercel", category: "Deployment" },
];

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 60);
    const handleMouse = (e: MouseEvent) =>
      setMousePos({ x: e.clientX, y: e.clientY });
    window.addEventListener("scroll", handleScroll);
    window.addEventListener("mousemove", handleMouse);
    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("mousemove", handleMouse);
    };
  }, []);

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#050B18",
        color: "#F8FAFC",
        fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        overflowX: "hidden",
      }}
    >
      {/* Ambient mouse glow */}
      <div
        style={{
          position: "fixed",
          top: mousePos.y - 300,
          left: mousePos.x - 300,
          width: 600,
          height: 600,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)",
          pointerEvents: "none",
          zIndex: 0,
          transition: "top 0.1s ease, left 0.1s ease",
        }}
      />

      {/* ── NAVBAR ───────────────────────────────────── */}
      <nav
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          padding: "0 40px",
          height: "68px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          backgroundColor: scrolled
            ? "rgba(5, 11, 24, 0.92)"
            : "transparent",
          backdropFilter: scrolled ? "blur(20px)" : "none",
          borderBottom: scrolled
            ? "1px solid rgba(255,255,255,0.06)"
            : "none",
          transition: "all 0.3s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "38px",
              height: "38px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #3B82F6, #7C3AED)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "20px",
              boxShadow: "0 0 20px rgba(59,130,246,0.5)",
            }}
          >
            🛡️
          </div>
          <div>
            <span
              style={{
                fontWeight: 800,
                fontSize: "17px",
                background: "linear-gradient(90deg, #93C5FD, #C4B5FD)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              BORDER GUARD AI
            </span>
            <div
              style={{
                fontSize: "10px",
                color: "#64748B",
                letterSpacing: "2px",
                textTransform: "uppercase",
              }}
            >
              SIH 26188 — MHA / SSB
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <Link
            href="/login"
            style={{
              padding: "8px 18px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#CBD5E1",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: 500,
              transition: "all 0.2s ease",
            }}
          >
            Login
          </Link>
          <Link
            href="/"
            style={{
              padding: "8px 20px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #3B82F6, #6D28D9)",
              color: "#FFF",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: 600,
              boxShadow: "0 4px 16px rgba(59,130,246,0.4)",
              transition: "all 0.2s ease",
            }}
          >
            🚀 Enter Dashboard
          </Link>
        </div>
      </nav>

      {/* ── HERO ─────────────────────────────────────── */}
      <section
        style={{
          position: "relative",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          padding: "120px 24px 80px",
          zIndex: 1,
        }}
      >
        {/* Grid lines overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `
              linear-gradient(rgba(59,130,246,0.04) 1px, transparent 1px),
              linear-gradient(90deg, rgba(59,130,246,0.04) 1px, transparent 1px)
            `,
            backgroundSize: "60px 60px",
            zIndex: 0,
          }}
        />

        {/* Radial gradient glow */}
        <div
          style={{
            position: "absolute",
            top: "10%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "800px",
            height: "500px",
            background:
              "radial-gradient(ellipse, rgba(59,130,246,0.15) 0%, transparent 70%)",
            zIndex: 0,
          }}
        />

        <div style={{ position: "relative", zIndex: 1 }}>
          {/* Badge */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 16px",
              borderRadius: "50px",
              border: "1px solid rgba(59,130,246,0.3)",
              backgroundColor: "rgba(59,130,246,0.08)",
              fontSize: "12px",
              color: "#93C5FD",
              fontWeight: 600,
              letterSpacing: "1px",
              textTransform: "uppercase",
              marginBottom: "28px",
            }}
          >
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: "#3B82F6",
                animation: "pulse-dot 2s infinite",
              }}
            />
            Smart India Hackathon 2026 · Problem Statement SIH26188
          </div>

          <h1
            style={{
              fontSize: "clamp(2.8rem, 6vw, 5rem)",
              fontWeight: 900,
              lineHeight: 1.05,
              margin: "0 0 24px",
              letterSpacing: "-2px",
            }}
          >
            <span
              style={{
                background: "linear-gradient(135deg, #F8FAFC 0%, #CBD5E1 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              AI-Powered Fake Identity
            </span>
            <br />
            <span
              style={{
                background:
                  "linear-gradient(135deg, #3B82F6 0%, #7C3AED 50%, #EC4899 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              & Document Screening
            </span>
          </h1>

          <p
            style={{
              fontSize: "clamp(1rem, 2vw, 1.2rem)",
              color: "#94A3B8",
              maxWidth: "680px",
              margin: "0 auto 48px",
              lineHeight: 1.7,
            }}
          >
            A real-time border security intelligence platform for the{" "}
            <strong style={{ color: "#CBD5E1" }}>
              Ministry of Home Affairs / Sashastra Seema Bal
            </strong>
            . Detects forged passports, stolen identities, and sanctioned
            travellers using multi-layered AI forensics.
          </p>

          <div
            style={{
              display: "flex",
              gap: "16px",
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            <Link
              href="/"
              style={{
                padding: "16px 36px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #3B82F6 0%, #7C3AED 100%)",
                color: "#FFF",
                fontWeight: 700,
                fontSize: "15px",
                textDecoration: "none",
                boxShadow:
                  "0 8px 32px rgba(59,130,246,0.4), 0 0 0 1px rgba(59,130,246,0.2)",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.2s ease",
              }}
            >
              🚀 Launch Dashboard
            </Link>
            <Link
              href="/scanner"
              style={{
                padding: "16px 36px",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.12)",
                backgroundColor: "rgba(255,255,255,0.04)",
                color: "#F8FAFC",
                fontWeight: 600,
                fontSize: "15px",
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                transition: "all 0.2s ease",
              }}
            >
              🔍 Open Scanner
            </Link>
          </div>
        </div>
      </section>

      {/* ── STATS BAR ─────────────────────────────────── */}
      <section
        style={{
          position: "relative",
          zIndex: 1,
          padding: "0 40px 80px",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "16px",
          }}
        >
          {STATS.map((s) => (
            <div
              key={s.label}
              style={{
                padding: "28px 24px",
                borderRadius: "16px",
                background:
                  "linear-gradient(135deg, rgba(15,23,42,0.8) 0%, rgba(30,41,59,0.5) 100%)",
                border: "1px solid rgba(255,255,255,0.07)",
                backdropFilter: "blur(12px)",
                textAlign: "center",
                transition: "transform 0.2s ease, border-color 0.2s ease",
              }}
            >
              <div style={{ fontSize: "32px", marginBottom: "8px" }}>
                {s.icon}
              </div>
              <div
                style={{
                  fontSize: "2.2rem",
                  fontWeight: 900,
                  background: "linear-gradient(135deg, #3B82F6, #7C3AED)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  lineHeight: 1,
                  marginBottom: "8px",
                }}
              >
                {s.value}
              </div>
              <div style={{ color: "#94A3B8", fontSize: "14px", fontWeight: 500 }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES ──────────────────────────────────── */}
      <section
        style={{
          position: "relative",
          zIndex: 1,
          padding: "60px 40px 100px",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "64px" }}>
          <div
            style={{
              fontSize: "12px",
              color: "#7C3AED",
              fontWeight: 700,
              letterSpacing: "3px",
              textTransform: "uppercase",
              marginBottom: "16px",
            }}
          >
            Core Intelligence Capabilities
          </div>
          <h2
            style={{
              fontSize: "clamp(1.8rem, 4vw, 2.8rem)",
              fontWeight: 800,
              margin: 0,
              letterSpacing: "-1px",
            }}
          >
            Six-Layer Forensic Shield
          </h2>
          <p
            style={{
              color: "#64748B",
              marginTop: "16px",
              fontSize: "16px",
              maxWidth: "560px",
              margin: "16px auto 0",
            }}
          >
            Every document is processed through a multi-vector AI pipeline
            before a decision is rendered.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
            gap: "20px",
          }}
        >
          {FEATURES.map((f) => (
            <div
              key={f.title}
              style={{
                padding: "28px",
                borderRadius: "16px",
                background:
                  "linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.6) 100%)",
                border: `1px solid ${f.color}22`,
                position: "relative",
                overflow: "hidden",
                transition: "transform 0.25s ease, border-color 0.25s ease",
              }}
            >
              {/* Corner glow */}
              <div
                style={{
                  position: "absolute",
                  top: "-40px",
                  right: "-40px",
                  width: "120px",
                  height: "120px",
                  borderRadius: "50%",
                  backgroundColor: f.color,
                  opacity: 0.07,
                  filter: "blur(20px)",
                }}
              />
              <div
                style={{
                  width: "52px",
                  height: "52px",
                  borderRadius: "14px",
                  backgroundColor: `${f.color}18`,
                  border: `1px solid ${f.color}30`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "24px",
                  marginBottom: "18px",
                }}
              >
                {f.icon}
              </div>
              <h3
                style={{
                  fontSize: "17px",
                  fontWeight: 700,
                  margin: "0 0 10px",
                  color: "#F8FAFC",
                }}
              >
                {f.title}
              </h3>
              <p style={{ color: "#64748B", fontSize: "14px", lineHeight: 1.65, margin: 0 }}>
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── TECH STACK ─────────────────────────────────── */}
      <section
        style={{
          borderTop: "1px solid rgba(255,255,255,0.05)",
          borderBottom: "1px solid rgba(255,255,255,0.05)",
          padding: "48px 40px",
          backgroundColor: "rgba(15,23,42,0.4)",
        }}
      >
        <div
          style={{
            maxWidth: "1200px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            gap: "40px",
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          <span
            style={{
              color: "#475569",
              fontSize: "13px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "2px",
              whiteSpace: "nowrap",
            }}
          >
            Built with
          </span>
          {TECH_STACK.map((t) => (
            <div
              key={t.name}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span style={{ fontWeight: 700, fontSize: "14px", color: "#CBD5E1" }}>
                {t.name}
              </span>
              <span style={{ fontSize: "11px", color: "#475569", textTransform: "uppercase", letterSpacing: "1px" }}>
                {t.category}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────── */}
      <section
        style={{
          position: "relative",
          zIndex: 1,
          padding: "100px 40px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "600px",
            height: "300px",
            background:
              "radial-gradient(ellipse, rgba(124,58,237,0.12) 0%, transparent 70%)",
            zIndex: 0,
          }}
        />
        <div style={{ position: "relative", zIndex: 1, maxWidth: "640px", margin: "0 auto" }}>
          <h2
            style={{
              fontSize: "clamp(2rem, 4vw, 3rem)",
              fontWeight: 900,
              margin: "0 0 20px",
              letterSpacing: "-1px",
              background: "linear-gradient(135deg, #F8FAFC 0%, #93C5FD 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Ready to Secure the Border?
          </h2>
          <p style={{ color: "#64748B", fontSize: "16px", marginBottom: "40px", lineHeight: 1.7 }}>
            Access the full AI screening console, document scanner, supervisor
            hub, and real-time risk analytics — all in one platform.
          </p>
          <div style={{ display: "flex", gap: "16px", justifyContent: "center", flexWrap: "wrap" }}>
            <Link
              href="/"
              style={{
                padding: "18px 44px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #3B82F6 0%, #7C3AED 100%)",
                color: "#FFF",
                fontWeight: 700,
                fontSize: "16px",
                textDecoration: "none",
                boxShadow: "0 8px 40px rgba(59,130,246,0.35)",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              🛡️ Enter Ops Console
            </Link>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────── */}
      <footer
        style={{
          borderTop: "1px solid rgba(255,255,255,0.05)",
          padding: "32px 40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "16px",
          color: "#475569",
          fontSize: "13px",
        }}
      >
        <span>
          🛡️ SIH 26188 — AI-Based Fake Identity & Document Screening System · Ministry of Home Affairs
        </span>
        <div style={{ display: "flex", gap: "24px" }}>
          <Link href="/" style={{ color: "#475569", textDecoration: "none" }}>
            Dashboard
          </Link>
          <Link href="/scanner" style={{ color: "#475569", textDecoration: "none" }}>
            Scanner
          </Link>
          <Link href="/history" style={{ color: "#475569", textDecoration: "none" }}>
            History
          </Link>
        </div>
      </footer>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.4); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
