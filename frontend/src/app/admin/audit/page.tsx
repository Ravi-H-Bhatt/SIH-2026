"use client";

import React, { useEffect, useState } from "react";
import { auditApi } from "@/lib/api";
import { AuditLog } from "@/types";

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");

  const loadAuditLogs = async () => {
    setLoading(true);
    try {
      const data = await auditApi.getLogs({
        action: actionFilter || undefined,
        limit: 30,
      });
      setLogs(data.logs);
    } catch (err) {
      console.error("Failed to load audit logs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditLogs();
  }, [actionFilter]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 6px" }}>
            Tamper-Evident System Audit Trail
          </h1>
          <p style={{ fontSize: "14px", color: "#94A3B8", margin: 0 }}>
            Immutable security log tracking officer actions, decisions, and system access
          </p>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          style={{
            padding: "10px 16px",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "8px",
            color: "#F8FAFC",
            fontSize: "14px",
            outline: "none",
          }}
        >
          <option value="">All Action Types</option>
          <option value="create_scan">Document Scan Upload</option>
          <option value="decision_approved">Clearance Approved</option>
          <option value="decision_flagged">Flagged for Secondary</option>
          <option value="decision_detained">Detained Passenger</option>
          <option value="login">User Login</option>
        </select>
      </div>

      {/* Audit Log Table */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ backgroundColor: "rgba(30, 41, 59, 0.4)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: "12px", textTransform: "uppercase" }}>
              <th style={{ padding: "14px 24px" }}>Timestamp</th>
              <th style={{ padding: "14px 24px" }}>Action</th>
              <th style={{ padding: "14px 24px" }}>User / Officer ID</th>
              <th style={{ padding: "14px 24px" }}>Resource</th>
              <th style={{ padding: "14px 24px" }}>IP Address</th>
              <th style={{ padding: "14px 24px" }}>Log Details</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  Loading audit trail logs...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  No audit logs recorded yet.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                  <td style={{ padding: "16px 24px", color: "#94A3B8", fontSize: "13px", fontFamily: "monospace" }}>
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    <span
                      style={{
                        padding: "4px 8px",
                        borderRadius: "6px",
                        fontSize: "11px",
                        fontWeight: 600,
                        backgroundColor: "rgba(59, 130, 246, 0.15)",
                        color: "#93C5FD",
                        border: "1px solid rgba(59, 130, 246, 0.3)",
                      }}
                    >
                      {log.action.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC" }}>
                    {log.user_id ? log.user_id.substring(0, 8) + "..." : "System"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#CBD5E1" }}>
                    {log.resource_type ? `${log.resource_type} (${log.resource_id?.substring(0, 6)}...)` : "—"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#94A3B8", fontFamily: "monospace" }}>
                    {log.ip_address || "127.0.0.1"}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#CBD5E1", fontSize: "13px" }}>
                    {log.details ? JSON.stringify(log.details) : "—"}
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
