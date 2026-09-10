"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, logout, isLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  // NEXT_PUBLIC_BYPASS_AUTH is gone. It let the whole app render with an
  // injected fake admin and no backend session at all.
  const PUBLIC_PATHS = ["/login", "/kiosk", "/landing", "/auth/callback"];
  const isPublic = PUBLIC_PATHS.includes(pathname);

  React.useEffect(() => {
    if (!isLoading && !user && !isPublic) {
      router.replace("/login");
    }
  }, [isLoading, user, isPublic, router]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (isLoading) {
    return (
      <div className="skeleton-container" style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F19', color: '#94A3B8' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#3B82F6', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }}></div>
          <p>Initializing Secure Border System...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const navItems = [
    { label: "Dashboard", href: "/", roles: ["admin", "officer", "supervisor", "investigator"], icon: "📊" },
    { label: "Supervisor Hub", href: "/supervisor", roles: ["admin", "supervisor"], icon: "👮‍♂️" },
    { label: "Document Scanner", href: "/scanner", roles: ["admin", "officer", "supervisor"], icon: "🔍" },
    { label: "Self-Service Kiosk", href: "/kiosk", roles: ["admin", "officer", "supervisor"], icon: "🛂" },
    // Biometric identification for travellers presenting no document: the face
    // is the query, matched 1:N against every stored encounter.
    { label: "Biometric Identification", href: "/face-search", roles: ["admin", "officer", "supervisor", "investigator"], icon: "🧬" },
    // Gallery of every screened traveller with their document and face images.
    { label: "Travellers", href: "/travellers", roles: ["admin", "officer", "supervisor", "investigator"], icon: "👥" },
    { label: "Scan History", href: "/history", roles: ["admin", "officer", "supervisor", "investigator"], icon: "📜" },
    { label: "User Management", href: "/admin/users", roles: ["admin"], icon: "👥" },
    { label: "Audit Logs", href: "/admin/audit", roles: ["admin", "supervisor", "investigator"], icon: "🛡️" },
  ];

  const filteredNav = navItems.filter((item) => item.roles.includes(user.role));

  // Route-level RBAC. Hiding a nav link is presentation, not access control — an
  // officer could still open /admin/users directly and see the page shell fire
  // requests. Block the render outright when the current path is not permitted
  // for this role. The backend independently enforces the same rules.
  const activeRoute = navItems.find(
    (item) => item.href !== "/" && pathname.startsWith(item.href)
  );
  if (activeRoute && !activeRoute.roles.includes(user.role)) {
    return (
      <div
        style={{
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0B0F19",
          padding: "24px",
        }}
      >
        <div style={{ textAlign: "center", maxWidth: "420px" }}>
          <div style={{ fontSize: "40px", marginBottom: "16px" }}>🔒</div>
          <h1 style={{ color: "#F8FAFC", fontSize: "20px", margin: "0 0 12px" }}>
            Access restricted
          </h1>
          <p style={{ color: "#94A3B8", fontSize: "14px", margin: "0 0 24px", lineHeight: 1.6 }}>
            Your role ({user.role}) is not authorised to view this section.
          </p>
          <Link
            href="/"
            style={{
              color: "#93C5FD",
              fontSize: "14px",
              textDecoration: "none",
              border: "1px solid rgba(255,255,255,0.15)",
              padding: "10px 20px",
              borderRadius: "8px",
            }}
          >
            Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", backgroundColor: "var(--bg-primary)" }}>
      {/* Sidebar */}
      <aside
        style={{
          width: "260px",
          backgroundColor: "var(--bg-secondary)",
          borderRight: "1px solid var(--border-color)",
          display: "flex",
          flexDirection: "column",
          position: "fixed",
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 100,
        }}
      >
        {/* Brand Header */}
        <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border-color)", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ width: "36px", height: "36px", borderRadius: "10px", background: "linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold", fontSize: "18px", color: "#FFF", boxShadow: "0 0 15px rgba(59, 130, 246, 0.4)" }}>
            🛡️
          </div>
          <div>
            <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#F8FAFC", margin: 0, letterSpacing: "-0.3px" }}>
              BORDER GUARD
            </h2>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
              AI Screening System
            </span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav style={{ flex: 1, padding: "16px 12px" }}>
          <div style={{ fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "1px", padding: "0 12px 12px" }}>
            Main Menu
          </div>
          {filteredNav.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 16px",
                  borderRadius: "8px",
                  marginBottom: "4px",
                  textDecoration: "none",
                  fontSize: "14px",
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? "#F8FAFC" : "var(--text-secondary)",
                  backgroundColor: isActive ? "rgba(59, 130, 246, 0.15)" : "transparent",
                  borderLeft: isActive ? "3px solid #3B82F6" : "3px solid transparent",
                  transition: "all 0.2s ease",
                }}
              >
                <span style={{ fontSize: "16px" }}>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div style={{ padding: "16px", borderTop: "1px solid var(--border-color)", backgroundColor: "rgba(15, 23, 42, 0.6)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" }}>
            <div style={{ width: "38px", height: "38px", borderRadius: "50%", backgroundColor: "#1E293B", border: "1px solid #334155", display: "flex", alignItems: "center", justifyContent: "center", color: "#3B82F6", fontWeight: "bold", fontSize: "14px" }}>
              {user.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
            </div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <p style={{ fontSize: "13px", fontWeight: 600, color: "#F8FAFC", margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {user.full_name}
              </p>
              <span style={{ fontSize: "11px", textTransform: "capitalize", padding: "2px 8px", borderRadius: "12px", backgroundColor: user.role === "admin" ? "rgba(239, 68, 68, 0.2)" : "rgba(59, 130, 246, 0.2)", color: user.role === "admin" ? "#FCA5A5" : "#93C5FD", display: "inline-block", marginTop: "2px" }}>
                {user.role}
              </span>
            </div>
          </div>
          <button
            onClick={logout}
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "6px",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              color: "#EF4444",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              transition: "all 0.2s ease",
            }}
          >
            🚪 Logout
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, marginLeft: "260px", display: "flex", flexDirection: "column" }}>
        {/* Top Header */}
        <header
          style={{
            height: "64px",
            borderBottom: "1px solid var(--border-color)",
            backgroundColor: "rgba(15, 23, 42, 0.8)",
            backdropFilter: "blur(12px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 32px",
            position: "sticky",
            top: 0,
            zIndex: 90,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#10B981", backgroundColor: "rgba(16, 185, 129, 0.1)", padding: "4px 10px", borderRadius: "12px", border: "1px solid rgba(16, 185, 129, 0.2)" }}>
              <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#10B981", animation: "pulse 2s infinite" }}></span>
              SYSTEM ONLINE
            </span>
            <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>
              Checkpoint: <strong style={{ color: "#F8FAFC" }}>Gate 04 — Airport Intl</strong>
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
            </span>
          </div>
        </header>

        {/* Page Viewport */}
        <main style={{ flex: 1, padding: "32px" }}>{children}</main>
      </div>
    </div>
  );
}
