"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { dashboardApi, scansApi } from "@/lib/api";
import { DashboardStats, ScanRecord } from "@/types";
import OperationsMapPanel from "@/components/OperationsMapPanel";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentScans, setRecentScans] = useState<ScanRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setError(null);
        // Fetch data with error handling
        try {
          const statsData = await dashboardApi.getStats();
          setStats(statsData);
        } catch (statsErr) {
          console.warn("Stats fetch failed, using defaults:", statsErr);
          setStats({
            total_scans_today: 0,
            approved_today: 0,
            flagged_today: 0,
            risk_breakdown: { low: 0, medium: 0, high: 0, critical: 0 },
          });
        }

        try {
          const scansData = await scansApi.getScans({ page_size: 5 });
          setRecentScans(scansData.scans || []);
        } catch (scansErr) {
          console.warn("Scans fetch failed:", scansErr);
          setRecentScans([]);
        }
      } catch (err: any) {
        console.error("Dashboard error:", err);
        setError("Unable to load dashboard data - Running with defaults");
      } finally {
        setLoading(false);
      }
    }
    loadDashboardData();
  }, []);

  const getRiskBadge = (level?: string) => {
    const l = (level || "low").toLowerCase();
    const map: Record<string, { bg: string; color: string; border: string }> = {
      low: { bg: "rgba(16, 185, 129, 0.15)", color: "#34D399", border: "rgba(16, 185, 129, 0.3)" },
      medium: { bg: "rgba(245, 158, 11, 0.15)", color: "#FBBF24", border: "rgba(245, 158, 11, 0.3)" },
      high: { bg: "rgba(239, 68, 68, 0.15)", color: "#FCA5A5", border: "rgba(239, 68, 68, 0.3)" },
      critical: { bg: "rgba(185, 28, 28, 0.25)", color: "#EF4444", border: "rgba(239, 68, 68, 0.5)" },
    };
    const style = map[l] || map.low;
    return (
      <span
        style={{
          padding: "4px 10px",
          borderRadius: "12px",
          fontSize: "11px",
          fontWeight: 600,
          textTransform: "uppercase",
          backgroundColor: style.bg,
          color: style.color,
          border: `1px solid ${style.border}`,
        }}
      >
        {level || "LOW"}
      </span>
    );
  };

  const getStatusBadge = (status?: string) => {
    const s = (status || "pending").toLowerCase();
    const map: Record<string, { bg: string; color: string }> = {
      approved: { bg: "rgba(16, 185, 129, 0.2)", color: "#34D399" },
      flagged: { bg: "rgba(245, 158, 11, 0.2)", color: "#FBBF24" },
      detained: { bg: "rgba(239, 68, 68, 0.2)", color: "#FCA5A5" },
      completed: { bg: "rgba(16, 185, 129, 0.2)", color: "#34D399" },
      pending: { bg: "rgba(148, 163, 184, 0.2)", color: "#CBD5E1" },
    };
    const style = map[s] || map.pending;
    return (
      <span style={{ padding: "4px 8px", borderRadius: "6px", fontSize: "12px", fontWeight: 500, backgroundColor: style.bg, color: style.color }}>
        {(status || "PENDING").toUpperCase()}
      </span>
    );
  };

  return (
    <div>
      {/* Top Banner Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 6px" }}>
            Border Security Operations Control
          </h1>
          <p style={{ fontSize: "14px", color: "#94A3B8", margin: 0 }}>
            Real-time document verification, forgery detection & risk analytics
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px" }}>
          <Link
            href="/scanner"
            style={{
              padding: "12px 20px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
              color: "#FFF",
              fontWeight: 600,
              fontSize: "14px",
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow: "0 4px 14px rgba(59, 130, 246, 0.4)",
            }}
          >
            🔍 Start New Document Scan
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "20px", marginBottom: "32px" }}>
        <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Total Scans Today
          </span>
          <p style={{ fontSize: "32px", fontWeight: 700, color: "#F8FAFC", margin: "12px 0 0" }}>
            {loading ? "..." : (stats?.total_scans_today ?? stats?.total_scans ?? 0)}
          </p>
        </div>

        <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Approved Clearances
          </span>
          <p style={{ fontSize: "32px", fontWeight: 700, color: "#34D399", margin: "12px 0 0" }}>
            {loading ? "..." : (stats?.approved_today ?? stats?.decisions_breakdown?.approved ?? 0)}
          </p>
        </div>

        <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Flagged for Secondary
          </span>
          <p style={{ fontSize: "32px", fontWeight: 700, color: "#FBBF24", margin: "12px 0 0" }}>
            {loading ? "..." : (stats?.flagged_today ?? stats?.decisions_breakdown?.flagged ?? 0)}
          </p>
        </div>

        <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            High / Critical Risk
          </span>
          <p style={{ fontSize: "32px", fontWeight: 700, color: "#EF4444", margin: "12px 0 0" }}>
            {loading ? "..." : ((stats?.risk_distribution?.high ?? 0) + (stats?.risk_distribution?.critical ?? 0)) || 0}
          </p>
        </div>
      </div>

      {/* Risk Distribution Breakdown */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "24px", marginBottom: "32px" }}>
        <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
          Today's Risk Profile Distribution
        </h3>
        <div style={{ height: "10px", borderRadius: "5px", backgroundColor: "#1E293B", overflow: "hidden", display: "flex", marginBottom: "12px" }}>
          <div style={{ width: `${((stats?.risk_distribution?.low ?? stats?.risk_breakdown?.low ?? 0) * 10)}%`, backgroundColor: "#10B981" }} title="Low Risk" />
          <div style={{ width: `${((stats?.risk_distribution?.medium ?? stats?.risk_breakdown?.medium ?? 0) * 10)}%`, backgroundColor: "#F59E0B" }} title="Medium Risk" />
          <div style={{ width: `${((stats?.risk_distribution?.high ?? stats?.risk_breakdown?.high ?? 0) * 10)}%`, backgroundColor: "#EF4444" }} title="High Risk" />
          <div style={{ width: `${((stats?.risk_distribution?.critical ?? stats?.risk_breakdown?.critical ?? 0) * 10)}%`, backgroundColor: "#7F1D1D" }} title="Critical Risk" />
        </div>
        <div style={{ display: "flex", gap: "24px", fontSize: "13px" }}>
          <span style={{ color: "#94A3B8" }}>🟢 Low: <strong style={{ color: "#F8FAFC" }}>{stats?.risk_distribution?.low ?? stats?.risk_breakdown?.low ?? 0}</strong></span>
          <span style={{ color: "#94A3B8" }}>🟡 Medium: <strong style={{ color: "#F8FAFC" }}>{stats?.risk_distribution?.medium ?? stats?.risk_breakdown?.medium ?? 0}</strong></span>
          <span style={{ color: "#94A3B8" }}>🔴 High: <strong style={{ color: "#F8FAFC" }}>{stats?.risk_distribution?.high ?? stats?.risk_breakdown?.high ?? 0}</strong></span>
          <span style={{ color: "#94A3B8" }}>⛔ Critical: <strong style={{ color: "#F8FAFC" }}>{stats?.risk_distribution?.critical ?? stats?.risk_breakdown?.critical ?? 0}</strong></span>
        </div>
      </div>

      {/* Operations Map */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "24px", marginBottom: "32px" }}>
        <OperationsMapPanel
          title="Operations Map"
          subtitle="Checkpoint activity and traveller origins by country of issue"
          height={430}
        />
      </div>

      {/* Recent Scans Table */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", overflow: "hidden" }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#F8FAFC", margin: 0 }}>
            Recent Document Scans
          </h3>
          <Link href="/history" style={{ fontSize: "13px", color: "#3B82F6", textDecoration: "none", fontWeight: 500 }}>
            View All Scans →
          </Link>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ backgroundColor: "rgba(30, 41, 59, 0.4)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: "12px", textTransform: "uppercase" }}>
              <th style={{ padding: "12px 24px" }}>Scan ID</th>
              <th style={{ padding: "12px 24px" }}>Document Type</th>
              <th style={{ padding: "12px 24px" }}>Document #</th>
              <th style={{ padding: "12px 24px" }}>Holder Name</th>
              <th style={{ padding: "12px 24px" }}>Risk Score</th>
              <th style={{ padding: "12px 24px" }}>Decision</th>
              <th style={{ padding: "12px 24px" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  Loading scan records...
                </td>
              </tr>
            ) : recentScans.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  No document scans recorded yet. <Link href="/scanner" style={{ color: "#3B82F6" }}>Perform a scan</Link>.
                </td>
              </tr>
            ) : (
              recentScans.map((scan) => (
                <tr key={scan.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                  <td style={{ padding: "16px 24px", fontFamily: "monospace", color: "#94A3B8" }}>
                    {scan.id.substring(0, 8)}...
                  </td>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC", textTransform: "uppercase", fontWeight: 500 }}>
                    {scan.document_type || "—"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#CBD5E1", fontFamily: "monospace" }}>
                    {scan.document_number || "A12345678"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC" }}>
                    {scan.holder_name || "NOT READ"}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    {getRiskBadge(scan.risk_score?.level || "low")}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    {getStatusBadge(scan.decision)}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    <Link
                      href={`/scans/${scan.id}`}
                      style={{
                        padding: "6px 12px",
                        backgroundColor: "rgba(59, 130, 246, 0.15)",
                        color: "#93C5FD",
                        borderRadius: "6px",
                        fontSize: "12px",
                        textDecoration: "none",
                        fontWeight: 500,
                      }}
                    >
                      View Report
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
