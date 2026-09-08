"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { scansApi } from "@/lib/api";
import { ScanRecord } from "@/types";

export default function ScanHistoryPage() {
  const [scans, setScans] = useState<ScanRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [decisionFilter, setDecisionFilter] = useState("");

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await scansApi.getScans({
        decision: decisionFilter || undefined,
        limit: 20,
      });
      setScans(data.scans);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load history", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [decisionFilter]);

  const filteredScans = scans.filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (s.holder_name && s.holder_name.toLowerCase().includes(q)) ||
      (s.document_number && s.document_number.toLowerCase().includes(q)) ||
      s.id.toLowerCase().includes(q)
    );
  });

  const getRiskBadge = (level: string) => {
    const map: Record<string, { bg: string; color: string }> = {
      low: { bg: "rgba(16, 185, 129, 0.15)", color: "#34D399" },
      medium: { bg: "rgba(245, 158, 11, 0.15)", color: "#FBBF24" },
      high: { bg: "rgba(239, 68, 68, 0.15)", color: "#FCA5A5" },
      critical: { bg: "rgba(185, 28, 28, 0.3)", color: "#EF4444" },
    };
    const style = map[level?.toLowerCase()] || map.low;
    return (
      <span style={{ padding: "4px 8px", borderRadius: "12px", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", backgroundColor: style.bg, color: style.color }}>
        {level || "LOW"}
      </span>
    );
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 6px" }}>
            Border Document Scan Archive
          </h1>
          <p style={{ fontSize: "14px", color: "#94A3B8", margin: 0 }}>
            Comprehensive search & historical log of all processed document verifications
          </p>
        </div>
        <span style={{ fontSize: "13px", color: "#94A3B8" }}>
          Total Records: <strong style={{ color: "#F8FAFC" }}>{total}</strong>
        </span>
      </div>

      {/* Search & Filter Bar */}
      <div style={{ display: "flex", gap: "16px", marginBottom: "24px" }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="🔎 Search by Document #, Name, or Scan ID..."
          style={{
            flex: 1,
            padding: "12px 16px",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "8px",
            color: "#F8FAFC",
            fontSize: "14px",
            outline: "none",
          }}
        />

        <select
          value={decisionFilter}
          onChange={(e) => setDecisionFilter(e.target.value)}
          style={{
            padding: "12px 16px",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "8px",
            color: "#F8FAFC",
            fontSize: "14px",
            outline: "none",
          }}
        >
          <option value="">All Decisions</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="flagged">Flagged</option>
          <option value="detained">Detained</option>
        </select>
      </div>

      {/* History Table */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ backgroundColor: "rgba(30, 41, 59, 0.4)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: "12px", textTransform: "uppercase" }}>
              <th style={{ padding: "14px 24px" }}>Timestamp</th>
              <th style={{ padding: "14px 24px" }}>Scan ID</th>
              <th style={{ padding: "14px 24px" }}>Doc Type</th>
              <th style={{ padding: "14px 24px" }}>Document #</th>
              <th style={{ padding: "14px 24px" }}>Holder Name</th>
              <th style={{ padding: "14px 24px" }}>Risk</th>
              <th style={{ padding: "14px 24px" }}>Decision</th>
              <th style={{ padding: "14px 24px" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  Loading scan records...
                </td>
              </tr>
            ) : filteredScans.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  No matching scan records found.
                </td>
              </tr>
            ) : (
              filteredScans.map((scan) => (
                <tr key={scan.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                  <td style={{ padding: "16px 24px", color: "#94A3B8", fontSize: "13px" }}>
                    {new Date(scan.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "16px 24px", fontFamily: "monospace", color: "#94A3B8" }}>
                    {scan.id.substring(0, 8)}...
                  </td>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC", textTransform: "uppercase" }}>
                    {scan.document_type || "PASSPORT"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#CBD5E1", fontFamily: "monospace" }}>
                    {scan.document_number || "P12345678"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC" }}>
                    {scan.holder_name || "JOHN DOE"}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    {getRiskBadge(scan.risk_score?.level || "low")}
                  </td>
                  <td style={{ padding: "16px 24px", textTransform: "uppercase", fontSize: "12px", fontWeight: 600, color: scan.decision === "approved" ? "#34D399" : scan.decision === "flagged" ? "#FBBF24" : scan.decision === "detained" ? "#EF4444" : "#94A3B8" }}>
                    {scan.decision}
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
