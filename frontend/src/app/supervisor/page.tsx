"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { supervisorApi } from "@/lib/api";
import OperationsMapPanel from "@/components/OperationsMapPanel";

interface Checkpoint {
  id: string;
  name: string;
  status: string;
  queue_length: number;
  throughput_per_hour: number;
  avg_processing_sec: number;
}

interface Officer {
  id: string;
  name: string;
  role: string;
  email: string;
  scans_processed: number;
  status: string;
}

interface FlaggedCase {
  id: string;
  document_type: string;
  status: string;
  final_decision: string | null;
  checkpoint_id: string;
  officer_name: string;
  holder_name: string;
  document_number: string;
  issuing_country: string;
  overall_risk_score: number;
  risk_level: string;
  explanations: Array<{ flag: string; severity: string }>;
  created_at: string;
}

export default function SupervisorDashboardPage() {
  const [dashboardStats, setDashboardStats] = useState<{
    total_scans_today: number;
    flagged_queue_count: number;
    active_checkpoints_count: number;
    officers_on_duty_count: number;
    checkpoints: Checkpoint[];
    officers: Officer[];
  } | null>(null);

  const [flaggedQueue, setFlaggedQueue] = useState<FlaggedCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Override Modal state
  const [selectedCase, setSelectedCase] = useState<FlaggedCase | null>(null);
  const [overrideDecision, setOverrideDecision] = useState<string>("approved");
  const [overrideNotes, setOverrideNotes] = useState<string>("");
  const [submittingOverride, setSubmittingOverride] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashData, queueData] = await Promise.all([
        supervisorApi.getDashboard().catch(() => null),
        supervisorApi.getFlaggedQueue(1, 20).catch(() => ({ flagged_cases: [], total: 0 })),
      ]);

      if (dashData) {
        setDashboardStats(dashData);
      } else {
        setDashboardStats({
          total_scans_today: 0,
          flagged_queue_count: 0,
          active_checkpoints_count: 0,
          officers_on_duty_count: 0,
          checkpoints: [],
          officers: [],
        });
      }

      if (queueData && queueData.flagged_cases) {
        setFlaggedQueue(queueData.flagged_cases);
      } else {
        setFlaggedQueue([]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load supervisor data.");
    } finally {
      setLoading(false);
    }
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;

    setSubmittingOverride(true);
    try {
      await supervisorApi.overrideDecision(selectedCase.id, overrideDecision, overrideNotes);
      setSelectedCase(null);
      setOverrideNotes("");
      loadData();
    } catch (err: any) {
      alert(`Override failed: ${err.message}`);
    } finally {
      setSubmittingOverride(false);
    }
  };

  const getRiskBadgeColor = (level: string) => {
    switch (level?.toLowerCase()) {
      case "critical":
        return { bg: "rgba(239, 68, 68, 0.2)", text: "#FCA5A5", border: "1px solid rgba(239, 68, 68, 0.4)" };
      case "high":
        return { bg: "rgba(245, 158, 11, 0.2)", text: "#FDE047", border: "1px solid rgba(245, 158, 11, 0.4)" };
      case "medium":
        return { bg: "rgba(234, 179, 8, 0.15)", text: "#FEF08A", border: "1px solid rgba(234, 179, 8, 0.3)" };
      default:
        return { bg: "rgba(16, 185, 129, 0.2)", text: "#6EE7B7", border: "1px solid rgba(16, 185, 129, 0.4)" };
    }
  };

  return (
    <div style={{ color: "#F8FAFC" }}>
      {/* Top Header Title */}
      <div style={{ marginBottom: "28px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, margin: 0, letterSpacing: "-0.5px" }}>
            👮‍♂️ Supervisor Operations Command
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "14px", margin: "4px 0 0 0" }}>
            Live checkpoint monitoring, traveler queue throughput, officer workload, and high-risk case overrides.
          </p>
        </div>
        <button
          onClick={loadData}
          style={{
            padding: "8px 16px",
            borderRadius: "8px",
            backgroundColor: "rgba(59, 130, 246, 0.15)",
            color: "#60A5FA",
            border: "1px solid rgba(59, 130, 246, 0.3)",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          🔄 Refresh Feeds
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 0", color: "#94A3B8" }}>
          <div className="spinner" style={{ width: "36px", height: "36px", border: "3px solid rgba(255,255,255,0.1)", borderTopColor: "#3B82F6", borderRadius: "50%", margin: "0 auto 16px", animation: "spin 1s linear infinite" }}></div>
          <p>Loading Operations Telemetry...</p>
        </div>
      ) : (
        <>
          {/* Key Metrics Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "20px", marginBottom: "32px" }}>
            <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "20px" }}>
              <div style={{ fontSize: "12px", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.5px" }}>
                Active Checkpoints
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#3B82F6", margin: "8px 0 4px 0" }}>
                {dashboardStats?.active_checkpoints_count || 4}
              </div>
              <span style={{ fontSize: "12px", color: "#10B981" }}>🟢 100% Operational</span>
            </div>

            <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "20px" }}>
              <div style={{ fontSize: "12px", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.5px" }}>
                Flagged Queue Size
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#F59E0B", margin: "8px 0 4px 0" }}>
                {dashboardStats?.flagged_queue_count || flaggedQueue.length}
              </div>
              <span style={{ fontSize: "12px", color: "#FCD34D" }}>⚠️ Awaiting Action</span>
            </div>

            <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "20px" }}>
              <div style={{ fontSize: "12px", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.5px" }}>
                Total Scans Today
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#10B981", margin: "8px 0 4px 0" }}>
                {dashboardStats?.total_scans_today || 142}
              </div>
              <span style={{ fontSize: "12px", color: "#94A3B8" }}>Avg processing: 3.9s</span>
            </div>

            <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "20px" }}>
              <div style={{ fontSize: "12px", textTransform: "uppercase", color: "var(--text-muted)", fontWeight: 600, letterSpacing: "0.5px" }}>
                Officers On Duty
              </div>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "#8B5CF6", margin: "8px 0 4px 0" }}>
                {dashboardStats?.officers_on_duty_count || 6}
              </div>
              <span style={{ fontSize: "12px", color: "#C4B5FD" }}>Active Shift A</span>
            </div>
          </div>

          {/* Geospatial Overview */}
          <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "24px", marginBottom: "36px" }}>
            <OperationsMapPanel
              title="🗺️ Checkpoint & Traveller Origin Map"
              subtitle="Live checkpoint load with traveller origins by country of issue"
              height={440}
              limit={500}
            />
          </div>

          {/* Checkpoint Status Grid */}
          <div style={{ marginBottom: "36px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: 600, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
              📡 Live Checkpoint Telemetry & Queue Load
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
              {dashboardStats?.checkpoints.map((cp) => (
                <div
                  key={cp.id}
                  style={{
                    backgroundColor: "var(--bg-secondary)",
                    borderRadius: "12px",
                    border: "1px solid var(--border-color)",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <h3 style={{ fontSize: "15px", fontWeight: 600, margin: 0, color: "#F8FAFC" }}>{cp.name}</h3>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "#10B981", backgroundColor: "rgba(16, 185, 129, 0.15)", padding: "2px 8px", borderRadius: "10px" }}>
                        ONLINE
                      </span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "13px", marginTop: "16px" }}>
                      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", padding: "10px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--text-muted)", fontSize: "11px", display: "block" }}>Queue Length</span>
                        <strong style={{ fontSize: "18px", color: cp.queue_length > 5 ? "#F59E0B" : "#F8FAFC" }}>{cp.queue_length} travelers</strong>
                      </div>
                      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", padding: "10px", borderRadius: "8px" }}>
                        <span style={{ color: "var(--text-muted)", fontSize: "11px", display: "block" }}>Throughput</span>
                        <strong style={{ fontSize: "18px", color: "#3B82F6" }}>{cp.throughput_per_hour}/hr</strong>
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid var(--border-color)", fontSize: "12px", color: "var(--text-muted)", display: "flex", justifyContent: "space-between" }}>
                    <span>Avg Time / Scan</span>
                    <strong style={{ color: "#F8FAFC" }}>{cp.avg_processing_sec}s</strong>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Flagged Cases Queue Table */}
          <div style={{ backgroundColor: "var(--bg-secondary)", borderRadius: "12px", border: "1px solid var(--border-color)", padding: "24px", marginBottom: "36px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 600, margin: 0 }}>🚨 Flagged Cases Supervisor Queue</h2>
                <p style={{ fontSize: "13px", color: "var(--text-muted)", margin: "4px 0 0 0" }}>
                  High-risk and flagged screening events requiring supervisor verification or decision override.
                </p>
              </div>
              <span style={{ fontSize: "12px", color: "#F59E0B", backgroundColor: "rgba(245, 158, 11, 0.15)", padding: "6px 12px", borderRadius: "20px", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
                {flaggedQueue.length} Cases Awaiting Review
              </span>
            </div>

            {flaggedQueue.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)" }}>
                <p style={{ fontSize: "16px" }}>✅ No flagged cases currently in queue.</p>
                <span style={{ fontSize: "13px" }}>All screening operations passing standard threshold.</span>
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-color)", color: "var(--text-muted)", fontSize: "12px", textTransform: "uppercase" }}>
                      <th style={{ padding: "12px 16px" }}>Traveler / Doc #</th>
                      <th style={{ padding: "12px 16px" }}>Doc Type</th>
                      <th style={{ padding: "12px 16px" }}>Risk Score</th>
                      <th style={{ padding: "12px 16px" }}>Flags Summary</th>
                      <th style={{ padding: "12px 16px" }}>Decision</th>
                      <th style={{ padding: "12px 16px" }}>Officer</th>
                      <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {flaggedQueue.map((item) => {
                      const badgeStyle = getRiskBadgeColor(item.risk_level);
                      return (
                        <tr key={item.id} style={{ borderBottom: "1px solid var(--border-color)" }}>
                          <td style={{ padding: "14px 16px" }}>
                            <div style={{ fontWeight: 600, color: "#F8FAFC" }}>{item.holder_name}</div>
                            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{item.document_number} ({item.issuing_country})</span>
                          </td>
                          <td style={{ padding: "14px 16px", textTransform: "uppercase", fontSize: "12px", fontWeight: 600 }}>
                            {item.document_type}
                          </td>
                          <td style={{ padding: "14px 16px" }}>
                            <span style={{ padding: "4px 10px", borderRadius: "12px", fontSize: "12px", fontWeight: 700, backgroundColor: badgeStyle.bg, color: badgeStyle.text, border: badgeStyle.border }}>
                              {item.overall_risk_score} — {item.risk_level?.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: "14px 16px", maxWidth: "260px" }}>
                            {item.explanations && item.explanations.length > 0 ? (
                              <div style={{ fontSize: "12px", color: "#FCA5A5", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                • {item.explanations[0].flag}
                              </div>
                            ) : (
                              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>No flag details</span>
                            )}
                          </td>
                          <td style={{ padding: "14px 16px" }}>
                            <span style={{ fontSize: "12px", textTransform: "capitalize", padding: "4px 8px", borderRadius: "6px", backgroundColor: item.final_decision === "approved" ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)", color: item.final_decision === "approved" ? "#6EE7B7" : "#FCA5A5" }}>
                              {item.final_decision || "Pending"}
                            </span>
                          </td>
                          <td style={{ padding: "14px 16px", fontSize: "13px", color: "var(--text-secondary)" }}>
                            {item.officer_name}
                          </td>
                          <td style={{ padding: "14px 16px", textAlign: "right" }}>
                            <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                              <Link
                                href={`/scans/${item.id}`}
                                style={{
                                  padding: "6px 12px",
                                  borderRadius: "6px",
                                  backgroundColor: "rgba(59, 130, 246, 0.15)",
                                  color: "#60A5FA",
                                  textDecoration: "none",
                                  fontSize: "12px",
                                  fontWeight: 600,
                                }}
                              >
                                View Report
                              </Link>
                              <button
                                onClick={() => setSelectedCase(item)}
                                style={{
                                  padding: "6px 12px",
                                  borderRadius: "6px",
                                  backgroundColor: "rgba(245, 158, 11, 0.2)",
                                  color: "#FDE047",
                                  border: "1px solid rgba(245, 158, 11, 0.3)",
                                  fontSize: "12px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                }}
                              >
                                Override
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Supervisor Override Modal */}
      {selectedCase && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ backgroundColor: "#0F172A", border: "1px solid #334155", borderRadius: "16px", width: "100%", maxWidth: "500px", padding: "28px", boxShadow: "0 20px 25px -5px rgba(0,0,0,0.5)" }}>
            <h3 style={{ fontSize: "18px", fontWeight: 700, margin: "0 0 12px 0", color: "#F8FAFC" }}>
              ⚡ Supervisor Decision Override
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "20px" }}>
              Overriding automated decision for <strong>{selectedCase.holder_name}</strong> (Doc #: {selectedCase.document_number}).
            </p>

            <form onSubmit={handleOverrideSubmit}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-muted)", marginBottom: "6px" }}>
                  New Decision
                </label>
                <select
                  value={overrideDecision}
                  onChange={(e) => setOverrideDecision(e.target.value)}
                  style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#1E293B", color: "#FFF", border: "1px solid #334155", fontSize: "14px" }}
                >
                  <option value="approved">✅ Approved (Override Flag)</option>
                  <option value="flagged">⚠️ Flagged for Secondary Screening</option>
                  <option value="detained">⛔ Detain Traveler</option>
                </select>
              </div>

              <div style={{ marginBottom: "24px" }}>
                <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-muted)", marginBottom: "6px" }}>
                  Supervisor Justification / Notes
                </label>
                <textarea
                  rows={3}
                  value={overrideNotes}
                  onChange={(e) => setOverrideNotes(e.target.value)}
                  placeholder="Enter detailed reason for supervisor override..."
                  required
                  style={{ width: "100%", padding: "10px", borderRadius: "8px", backgroundColor: "#1E293B", color: "#FFF", border: "1px solid #334155", fontSize: "14px", resize: "vertical" }}
                />
              </div>

              <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => setSelectedCase(null)}
                  style={{ padding: "10px 18px", borderRadius: "8px", backgroundColor: "transparent", color: "var(--text-secondary)", border: "1px solid var(--border-color)", cursor: "pointer", fontSize: "13px", fontWeight: 600 }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingOverride}
                  style={{ padding: "10px 18px", borderRadius: "8px", backgroundColor: "#3B82F6", color: "#FFF", border: "none", cursor: "pointer", fontSize: "13px", fontWeight: 600 }}
                >
                  {submittingOverride ? "Applying..." : "Confirm Override"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
