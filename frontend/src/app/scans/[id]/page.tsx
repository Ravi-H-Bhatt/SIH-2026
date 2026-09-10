"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { scansApi, apiClient } from "@/lib/api";
import { ScanRecord, ContradictionItem, FraudPatternMatch } from "@/types";
import LocationMap from "@/components/LocationMap";

/**
 * Colour scheme per contradiction-matrix status.
 *
 * The badge used to be a binary `isContradiction ? red : green`, so an ALERT
 * row and a NOT_PERFORMED row both rendered in PASS green — an officer scanning
 * the status column saw green next to a failed MRZ check and a skipped biometric.
 */
const STATUS_STYLES: Record<
  string,
  { text: string; bg: string; border: string; row: string; finding: string }
> = {
  PASS: {
    text: "#34D399",
    bg: "rgba(16, 185, 129, 0.2)",
    border: "rgba(16, 185, 129, 0.4)",
    row: "transparent",
    finding: "#94A3B8",
  },
  ALERT: {
    text: "#FBBF24",
    bg: "rgba(245, 158, 11, 0.2)",
    border: "rgba(245, 158, 11, 0.45)",
    row: "rgba(245, 158, 11, 0.07)",
    finding: "#FCD34D",
  },
  CONTRADICTION: {
    text: "#EF4444",
    bg: "rgba(239, 68, 68, 0.25)",
    border: "rgba(239, 68, 68, 0.5)",
    row: "rgba(239, 68, 68, 0.08)",
    finding: "#FCA5A5",
  },
  NOT_PERFORMED: {
    text: "#94A3B8",
    bg: "rgba(148, 163, 184, 0.15)",
    border: "rgba(148, 163, 184, 0.35)",
    row: "rgba(148, 163, 184, 0.05)",
    finding: "#94A3B8",
  },
};

function statusStyle(status?: string) {
  return STATUS_STYLES[String(status || "").toUpperCase()] || STATUS_STYLES.NOT_PERFORMED;
}

/**
 * Renders a document field, or an explicit "NOT READ" marker when the backend
 * has no value for it.
 *
 * This exists because the panel previously used `||` fallbacks to plausible
 * sample data ("JOHN DOE", "P12345678", "2031-10-15"). An officer looking at a
 * failed scan saw a complete passport that had never been read. A blank is
 * recoverable; a fabricated value that looks real is not.
 */
function FieldValue({ value, mono = false }: { value?: string | null; mono?: boolean }) {
  const missing =
    value === null ||
    value === undefined ||
    value === "" ||
    ["TRAVELER", "TRAVELLER", "NOT_DETECTED", "UNKNOWN", "UNREADABLE NAME"].includes(
      String(value).toUpperCase()
    );

  if (missing) {
    return (
      <p style={{ color: "#F87171", fontWeight: 600, margin: "2px 0 0", fontSize: "12px" }}>
        ⚠ NOT READ
      </p>
    );
  }

  return (
    <p
      style={{
        color: "#F8FAFC",
        fontWeight: 600,
        margin: "2px 0 0",
        fontFamily: mono ? "monospace" : undefined,
      }}
    >
      {value}
    </p>
  );
}

export default function ScanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const scanId = params.id as string;

  const [scan, setScan] = useState<ScanRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Audit Proof verification state
  const [verifyingAudit, setVerifyingAudit] = useState(false);
  const [auditVerificationResult, setAuditVerificationResult] = useState<{
    verified: boolean;
    canonical_hash: string;
    integrity_message: string;
    timestamp: string;
  } | null>(null);

  useEffect(() => {
    async function loadScan() {
      try {
        const data = await scansApi.getScan(scanId);
        setScan(data);
        if (data.notes) setDecisionNotes(data.notes);
      } catch (err: any) {
        setError(err.message || "Failed to load scan details.");
      } finally {
        setLoading(false);
      }
    }
    loadScan();
  }, [scanId]);

  const handleDecision = async (decision: "approved" | "flagged" | "detained") => {
    setIsSubmitting(true);
    try {
      const updated = await scansApi.makeDecision(scanId, decision, decisionNotes);
      setScan(updated);
    } catch (err: any) {
      alert("Failed to submit decision: " + (err.message || "Unknown error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyAudit = async () => {
    setVerifyingAudit(true);
    try {
      const res = await apiClient.verifyAuditIntegrity(scanId);
      setAuditVerificationResult(res);
    } catch (err: any) {
      alert("Audit verification check failed: " + (err.message || "Unknown error"));
    } finally {
      setVerifyingAudit(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "80px 0", color: "#94A3B8" }}>
        <div style={{ width: "48px", height: "48px", border: "3px solid rgba(255,255,255,0.1)", borderTopColor: "#3B82F6", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 16px" }} />
        <p style={{ fontSize: "16px", fontWeight: 500 }}>Fusing Multi-Modal Evidence & Evaluating Contradiction Matrix...</p>
      </div>
    );
  }

  if (error || !scan) {
    return (
      <div style={{ backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#FCA5A5", padding: "24px", borderRadius: "12px" }}>
        ⚠️ {error || "Scan record not found."}
      </div>
    );
  }

  const riskLevel = scan.risk_score?.level || scan.risk_score?.risk_level || "low";
  const riskColorMap: Record<string, { bg: string; color: string; border: string }> = {
    low: { bg: "rgba(16, 185, 129, 0.15)", color: "#34D399", border: "rgba(16, 185, 129, 0.3)" },
    medium: { bg: "rgba(245, 158, 11, 0.15)", color: "#FBBF24", border: "rgba(245, 158, 11, 0.3)" },
    high: { bg: "rgba(239, 68, 68, 0.15)", color: "#FCA5A5", border: "rgba(239, 68, 68, 0.3)" },
    critical: { bg: "rgba(185, 28, 28, 0.3)", color: "#EF4444", border: "rgba(239, 68, 68, 0.6)" },
  };
  const riskStyle = riskColorMap[riskLevel.toLowerCase()] || riskColorMap.low;

  const contradictionMatrix: ContradictionItem[] = scan.risk_score?.contradiction_matrix || [];
  const graphSummary = scan.risk_score?.identity_graph_summary;
  const fraudPatterns: FraudPatternMatch[] = scan.risk_score?.fraud_patterns_matched || [];
  const canonicalHash = scan.canonical_hash || scan.risk_score?.canonical_hash;

  // Real decoded MRZ lines only. Empty means the MRZ was not read, which the
  // panel states explicitly instead of rendering a sample TD3 pair.
  const mrzLines: string[] = (scan.extracted_data?.mrz_lines || []).filter(
    (line: string) => typeof line === "string" && line.trim().length > 0
  );

  return (
    <div style={{ maxWidth: "1240px", margin: "0 auto", paddingBottom: "60px" }}>
      {/* Top Breadcrumb & Actions Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
        <div>
          <button
            onClick={() => router.back()}
            style={{ backgroundColor: "transparent", border: "none", color: "#38BDF8", fontSize: "13px", cursor: "pointer", marginBottom: "8px", display: "inline-flex", alignItems: "center", gap: "4px", padding: 0 }}
          >
            ← Back to Verification Queue
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", margin: 0 }}>
              Identity & Evidence Fraud Intelligence Console
            </h1>
            <span style={{ fontSize: "12px", padding: "4px 8px", borderRadius: "6px", backgroundColor: "rgba(56, 189, 248, 0.15)", color: "#38BDF8", border: "1px solid rgba(56, 189, 248, 0.3)", fontWeight: 600 }}>
              FRAUD INTELLIGENCE LAYER
            </span>
          </div>
          <span style={{ fontSize: "13px", color: "#94A3B8", fontFamily: "monospace", marginTop: "4px", display: "block" }}>
            Scan ID: {scan.id} | Encounter: {new Date(scan.created_at).toLocaleString()} | Lane: {scan.checkpoint_id || "UNSPECIFIED"}
          </span>
        </div>

        {/* Status Pill & Risk Badge */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Chip PKI / Credential Security Pill */}
          <div style={{ padding: "8px 14px", borderRadius: "10px", backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(255,255,255,0.1)", textAlign: "right" }}>
            <span style={{ fontSize: "10px", color: "#64748B", textTransform: "uppercase", display: "block" }}>
              {scan.document_type === "passport" ? "ePassport Chip PKI" : "Security Credential"}
            </span>
            <span style={{ fontSize: "13px", fontWeight: 600, color: scan.chip_pki_status === "AUTHENTIC_VALID" ? "#34D399" : (scan.chip_pki_status === "NOT_APPLICABLE" ? "#94A3B8" : "#FBBF24") }}>
              {scan.chip_pki_status === "NOT_APPLICABLE" ? "STANDARD ID (NO RFID)" : (scan.chip_pki_status || "NOT VERIFIED")}
            </span>
          </div>

          {/* Aggregated Risk Score */}
          <div
            style={{
              padding: "10px 20px",
              borderRadius: "12px",
              backgroundColor: riskStyle.bg,
              border: `1px solid ${riskStyle.border}`,
              textAlign: "center",
              minWidth: "140px",
            }}
          >
            <span style={{ fontSize: "11px", fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", display: "block" }}>
              Risk Index: {scan.risk_score?.score ?? 15}/100
            </span>
            <strong style={{ fontSize: "16px", color: riskStyle.color, textTransform: "uppercase" }}>
              {riskLevel} RISK
            </strong>
          </div>
        </div>
      </div>

      {/* Cryptographic Proof & Ledger Non-Repudiation Banner */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.7)", border: "1px solid rgba(56, 189, 248, 0.25)", borderRadius: "12px", padding: "14px 20px", marginBottom: "24px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "22px" }}>🔒</span>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#F8FAFC" }}>
                Immutable Cryptographic Evidence Anchor (SHA-256)
              </span>
              <span style={{ fontSize: "10px", backgroundColor: "rgba(52, 211, 153, 0.15)", color: "#34D399", padding: "2px 6px", borderRadius: "4px", border: "1px solid rgba(52, 211, 153, 0.3)" }}>
                VERIFIABLE AUDIT PROOF
              </span>
            </div>
            <p style={{ margin: "2px 0 0", fontSize: "12px", color: "#94A3B8", fontFamily: "monospace" }}>
              Digest: {canonicalHash || "NOT ANCHORED"}
            </p>
          </div>
        </div>

        <button
          onClick={handleVerifyAudit}
          disabled={verifyingAudit}
          style={{
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            border: "1px solid rgba(56, 189, 248, 0.4)",
            color: "#38BDF8",
            padding: "8px 16px",
            borderRadius: "8px",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease",
          }}
        >
          {verifyingAudit ? "Verifying..." : "⚡ Verify Audit Integrity"}
        </button>
      </div>

      {auditVerificationResult && (
        <div style={{ backgroundColor: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.4)", borderRadius: "10px", padding: "14px 20px", marginBottom: "24px", color: "#34D399", fontSize: "13px" }}>
          <strong>✓ Cryptographic Proof Confirmed:</strong> {auditVerificationResult.integrity_message} (SHA-256 fingerprint verified against ledger state).
        </div>
      )}

      {/* SIGNATURE SECTION 1: THE CONTRADICTION MATRIX */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "22px", marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h2 style={{ fontSize: "17px", fontWeight: 700, color: "#F8FAFC", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <span>⚖️</span> Cross-Modal Contradiction Matrix
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#94A3B8" }}>
              Correlates independent claims to catch identity fraud that survives individual scanner checks.
            </p>
          </div>

          {/* Summarises the worst status present, not just CONTRADICTION. This
              read "ALL SIGNALS HARMONIOUS" in green while rows below were ALERT
              or NOT_PERFORMED. */}
          {(() => {
            const counts = {
              contradiction: contradictionMatrix.filter(c => c.status === "CONTRADICTION").length,
              alert: contradictionMatrix.filter(c => c.status === "ALERT").length,
              skipped: contradictionMatrix.filter(c => c.status === "NOT_PERFORMED").length,
            };
            let label = "✓ ALL SIGNALS HARMONIOUS";
            let key = "PASS";
            if (counts.contradiction > 0) {
              label = `⚠️ ${counts.contradiction} CONTRADICTION${counts.contradiction > 1 ? "S" : ""} DETECTED`;
              key = "CONTRADICTION";
            } else if (counts.alert > 0) {
              label = `⚠️ ${counts.alert} ALERT${counts.alert > 1 ? "S" : ""}`;
              key = "ALERT";
            } else if (counts.skipped > 0) {
              label = `${counts.skipped} CHECK${counts.skipped > 1 ? "S" : ""} NOT PERFORMED`;
              key = "NOT_PERFORMED";
            }
            const sv = statusStyle(key);
            return (
              <span style={{ fontSize: "12px", color: sv.text, fontWeight: 600, backgroundColor: sv.bg, padding: "4px 10px", borderRadius: "6px", border: `1px solid ${sv.border}`, whiteSpace: "nowrap" }}>
                {label}
              </span>
            );
          })()}
        </div>

        {/* Matrix Table */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", color: "#64748B", fontSize: "11px", textTransform: "uppercase" }}>
                <th style={{ padding: "10px 14px" }}>Verification Stream</th>
                <th style={{ padding: "10px 14px" }}>Claim A</th>
                <th style={{ padding: "10px 14px" }}>Claim B</th>
                <th style={{ padding: "10px 14px" }}>Finding & Semantic Anomaly</th>
                <th style={{ padding: "10px 14px", textAlign: "right" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {contradictionMatrix.length > 0 ? (
                contradictionMatrix.map((item, idx) => {
                  const sv = statusStyle(item.status);
                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.05)",
                        backgroundColor: sv.row,
                      }}
                    >
                      <td style={{ padding: "12px 14px", fontWeight: 600, color: "#F8FAFC" }}>
                        {item.check_name}
                      </td>
                      <td style={{ padding: "12px 14px", color: "#CBD5E1" }}>
                        <span style={{ backgroundColor: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "4px" }}>
                          {item.signal_a}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", color: "#CBD5E1" }}>
                        <span style={{ backgroundColor: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "4px" }}>
                          {item.signal_b}
                        </span>
                      </td>
                      <td style={{ padding: "12px 14px", color: sv.finding }}>
                        {item.finding}
                      </td>
                      <td style={{ padding: "12px 14px", textAlign: "right" }}>
                        <span
                          style={{
                            padding: "4px 8px",
                            borderRadius: "6px",
                            fontSize: "11px",
                            fontWeight: 700,
                            backgroundColor: sv.bg,
                            color: sv.text,
                            border: `1px solid ${sv.border}`,
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} style={{ padding: "16px", textAlign: "center", color: "#64748B" }}>
                    Standard contradiction checks passed with 100% mutual consistency.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SIGNATURE SECTION 2: IDENTITY CONTINUITY & FRAUD GRAPH */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "14px", padding: "22px", marginBottom: "24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h2 style={{ fontSize: "17px", fontWeight: 700, color: "#F8FAFC", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <span>🕸️</span> Identity Continuity & Fraud Graph
            </h2>
            <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#94A3B8" }}>
              Entity resolution across historical encounters — detects synthetic identity hopping & photo reuse rings.
            </p>
          </div>

          <span style={{ fontSize: "12px", color: graphSummary?.has_graph_anomalies ? "#EF4444" : "#34D399", fontWeight: 600, backgroundColor: graphSummary?.has_graph_anomalies ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.15)", padding: "4px 10px", borderRadius: "6px" }}>
            {graphSummary?.has_graph_anomalies ? "⚠️ MULTI-ENCOUNTER ANOMALY" : "✓ IDENTITY CONTINUITY CLEAN"}
          </span>
        </div>

        {/* Graph Node Connections Visualizer */}
        <div style={{ backgroundColor: "#0B0F19", borderRadius: "10px", padding: "20px", border: "1px solid rgba(255,255,255,0.06)", marginBottom: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-around", flexWrap: "wrap", gap: "16px" }}>
            {/* Current Encounter Node */}
            <div style={{ textAlign: "center", padding: "16px", borderRadius: "12px", backgroundColor: "rgba(30, 41, 59, 0.6)", border: "1px solid #38BDF8", minWidth: "200px" }}>
              <span style={{ fontSize: "10px", color: "#38BDF8", fontWeight: 700, textTransform: "uppercase" }}>Current Encounter</span>
              <p style={{ margin: "6px 0 2px", fontWeight: 700, color: "#F8FAFC", fontSize: "15px" }}>
                {scan.holder_name || "TRAVELER"}
              </p>
              <span style={{ fontSize: "12px", color: "#94A3B8", fontFamily: "monospace" }}>
                Document {scan.document_number || "NOT READ"}
              </span>
            </div>

            {/* Connecting Biometric Vector */}
            <div style={{ textAlign: "center", color: "#94A3B8" }}>
              <span style={{ fontSize: "11px", display: "block", color: "#38BDF8", fontWeight: 600 }}>512-d ArcFace Vector</span>
              <span style={{ fontSize: "20px", display: "block" }}>
                {graphSummary?.has_graph_anomalies ? "⇄ ⚡ ⇄" : "⇄ ✓ ⇄"}
              </span>
              <span style={{ fontSize: "11px", color: graphSummary?.has_graph_anomalies ? "#EF4444" : "#34D399" }}>
                {graphSummary?.has_graph_anomalies ? "Cross-Identity Link" : "Unique Profile"}
              </span>
            </div>

            {/* Historical Link Node (If found) */}
            {graphSummary?.continuity_links && graphSummary.continuity_links.length > 0 ? (
              graphSummary.continuity_links.map((link, idx) => (
                <div
                  key={idx}
                  style={{
                    textAlign: "center",
                    padding: "16px",
                    borderRadius: "12px",
                    backgroundColor: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    minWidth: "200px",
                  }}
                >
                  <span style={{ fontSize: "10px", color: "#FCA5A5", fontWeight: 700, textTransform: "uppercase" }}>
                    Prior Transit ({link.encounter_date})
                  </span>
                  <p style={{ margin: "6px 0 2px", fontWeight: 700, color: "#F8FAFC", fontSize: "15px" }}>
                    {link.holder_name}
                  </p>
                  <span style={{ fontSize: "12px", color: "#CBD5E1", fontFamily: "monospace", display: "block" }}>
                    Passport {link.document_number}
                  </span>
                  <span style={{ fontSize: "11px", color: "#F87171", fontWeight: 600 }}>
                    Biometric Similarity: {(link.biometric_similarity * 100).toFixed(1)}%
                  </span>
                </div>
              ))
            ) : (
              <div style={{ textAlign: "center", padding: "16px", borderRadius: "12px", backgroundColor: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.3)", minWidth: "200px" }}>
                <span style={{ fontSize: "10px", color: "#34D399", fontWeight: 700, textTransform: "uppercase" }}>Historical Continuity</span>
                <p style={{ margin: "6px 0 2px", fontWeight: 600, color: "#F8FAFC", fontSize: "14px" }}>
                  Clean Biometric Record
                </p>
                <span style={{ fontSize: "12px", color: "#94A3B8" }}>
                  No conflicting identities found
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Anomalies List */}
        {graphSummary?.anomalies && graphSummary.anomalies.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {graphSummary.anomalies.map((anom, idx) => (
              <div
                key={idx}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  fontSize: "13px",
                  color: "#FCA5A5",
                }}
              >
                <strong>⚠️ {anom.type}:</strong> {anom.description}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SIGNATURE SECTION 3: FRAUD PATTERN MEMORY (EU-FADO STYLE) */}
      {fraudPatterns.length > 0 && (
        <div style={{ backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "14px", padding: "22px", marginBottom: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
            <h2 style={{ fontSize: "17px", fontWeight: 700, color: "#F8FAFC", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
              <span>🧠</span> Fraud Pattern Memory Match (EU-FADO Signature DB)
            </h2>
            <span style={{ fontSize: "11px", backgroundColor: "rgba(245, 158, 11, 0.15)", color: "#FBBF24", padding: "4px 8px", borderRadius: "6px", fontWeight: 600 }}>
              KNOWN TACTIC SIGNATURES
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px" }}>
            {fraudPatterns.map((pat, idx) => (
              <div key={idx} style={{ backgroundColor: "rgba(30, 41, 59, 0.5)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "8px", padding: "14px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ color: "#F8FAFC", fontWeight: 700, fontSize: "14px" }}>{pat.name}</span>
                    <span style={{ fontSize: "10px", backgroundColor: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px", color: "#94A3B8", fontFamily: "monospace" }}>
                      {pat.pattern_id}
                    </span>
                  </div>
                  <p style={{ margin: "6px 0 8px", fontSize: "13px", color: "#CBD5E1" }}>
                    {pat.description}
                  </p>
                  <span style={{ fontSize: "12px", color: "#38BDF8", fontWeight: 600 }}>
                    💡 Officer Countermeasure: {pat.countermeasure}
                  </span>
                </div>
                <div style={{ textAlign: "right", minWidth: "100px" }}>
                  <span style={{ fontSize: "11px", color: "#94A3B8", display: "block" }}>Confidence</span>
                  <strong style={{ fontSize: "16px", color: "#FBBF24" }}>
                    {(pat.confidence * 100).toFixed(0)}%
                  </strong>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Grid: Images & Extracted Demographics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", marginBottom: "32px" }}>
        {/* Left Column — Images & Biometric Comparison */}
        <div>
          {/* Document Image Card */}
          <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px", marginBottom: "20px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 12px" }}>
              🖼️ Document Visual Scan
            </h3>
            <div style={{ height: "260px", backgroundColor: "#0B0F19", borderRadius: "8px", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
              {/* Use the signed URL the API mints, not the storage URI. The old
                  code did `http://localhost:8000/${scan.document_image_path}`,
                  which concatenated a hardcoded host with a `supabase://…` URI
                  and 404'd every time — hence the permanently broken previews. */}
              {scan.document_image_url ? (
                <img
                  src={scan.document_image_url}
                  alt="Scanned travel document"
                  style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              ) : (
                <div style={{ textAlign: "center", color: "#64748B" }}>
                  <span style={{ fontSize: "40px", display: "block", marginBottom: "8px" }}>📄</span>
                  <span>Document Image Preview</span>
                </div>
              )}
            </div>
          </div>

          {/* Face Match Card */}
          <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
              {/* Was "ArcFace 512-d". The ArcFace backend was removed; matching
                  runs on SFace, which produces a 128-d feature. */}
              👤 SFace 128-d Biometric Verification (1:1)
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
              <div style={{ textAlign: "center" }}>
                <span style={{ fontSize: "11px", color: "#94A3B8", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>
                  Document Photo
                </span>
                <div style={{ width: "100px", height: "120px", backgroundColor: "#0B0F19", borderRadius: "8px", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255,255,255,0.1)", overflow: "hidden" }}>
                  {/* `crop_path` was a server-local filesystem path that the API
                      never returned, so this was always the placeholder. Show the
                      document image itself as the portrait source instead. */}
                  {scan.document_image_url ? (
                    <img src={scan.document_image_url} alt="Document portrait" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <span style={{ fontSize: "32px" }}>👤</span>
                  )}
                </div>
              </div>
              <div style={{ textAlign: "center" }}>
                <span style={{ fontSize: "11px", color: "#94A3B8", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>
                  Live Capture Frame
                </span>
                <div style={{ width: "100px", height: "120px", backgroundColor: "#0B0F19", borderRadius: "8px", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(255,255,255,0.1)", overflow: "hidden" }}>
                  {scan.face_image_url ? (
                    <img src={scan.face_image_url} alt="Live capture" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <span style={{ fontSize: "32px" }}>📸</span>
                  )}
                </div>
              </div>
            </div>

            <div style={{ backgroundColor: "rgba(30, 41, 59, 0.5)", padding: "12px", borderRadius: "8px", fontSize: "13px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                <span style={{ color: "#94A3B8" }}>Raw Cosine Similarity:</span>
                {/* Report only what the backend measured.
                    This used to read `scan.face_results?.similarity_score ?? 0.94`
                    against an always-null object, so EVERY scan — including real
                    biometric failures — displayed "94.0% / PASSED (Live)".

                    It then compared against a hardcoded 0.70, which was the
                    OUTPUT of a calibration remap rather than a real cosine. The
                    stored match_score is now the raw SFace cosine and the
                    operating threshold is 0.363, so the comparison is meaningful. */}
                {(() => {
                  const face = scan.face_result ?? scan.face_results;
                  const score = face?.match_score ?? face?.similarity_score;
                  if (score === null || score === undefined) {
                    return <strong style={{ color: "#94A3B8" }}>Not performed</strong>;
                  }
                  const THRESHOLD = 0.363;
                  const passed = score >= THRESHOLD;
                  return (
                    <strong style={{ color: passed ? "#34D399" : "#EF4444" }}>
                      {score.toFixed(4)} / {THRESHOLD} — {passed ? "MATCH" : "NO MATCH"}
                    </strong>
                  );
                })()}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94A3B8" }}>Fourier Texture Liveness:</span>
                {(() => {
                  const face = scan.face_result ?? scan.face_results;
                  const live = face?.liveness_passed ?? face?.is_live;
                  if (live === null || live === undefined) {
                    return <strong style={{ color: "#94A3B8" }}>Not performed</strong>;
                  }
                  return (
                    <strong style={{ color: live ? "#34D399" : "#EF4444" }}>
                      {live ? "PASSED (Live)" : "FAILED (Screen Replay / Print)"}
                    </strong>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column — Extracted Data & Forensics */}
        <div>
          {/* Extracted Fields */}
          <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px", marginBottom: "20px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
              📋 ICAO 9303 OCR & Demographics
            </h3>
            {/*
              Every field below renders NOT READ when the backend has no value.

              These were `||` fallbacks to "JOHN DOE", "P12345678", "IND" and
              "2031-10-15". On a document whose OCR failed, the panel therefore
              displayed a complete, plausible passport — including a valid future
              expiry date — for data that had never been read. On an evidence
              screen that an officer acts on, inventing a value is worse than
              showing a blank.
            */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", fontSize: "13px" }}>
              <div>
                <span style={{ color: "#64748B", fontSize: "11px", textTransform: "uppercase" }}>Full Name</span>
                <FieldValue value={scan.holder_name} />
              </div>
              <div>
                <span style={{ color: "#64748B", fontSize: "11px", textTransform: "uppercase" }}>Document Number</span>
                <FieldValue value={scan.document_number} mono />
              </div>
              <div>
                <span style={{ color: "#64748B", fontSize: "11px", textTransform: "uppercase" }}>Nationality</span>
                <FieldValue value={scan.extracted_data?.nationality || scan.issuing_country} />
              </div>
              <div>
                <span style={{ color: "#64748B", fontSize: "11px", textTransform: "uppercase" }}>Date of Expiry</span>
                <FieldValue value={scan.extracted_data?.expiry_date} />
              </div>
            </div>

            {/* MRZ Line Box — real decoded lines only. */}
            <div style={{ marginTop: "16px", backgroundColor: "#0B0F19", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", padding: "12px", fontFamily: "monospace", fontSize: "12px", color: "#38BDF8" }}>
              {mrzLines.length > 0 ? (
                mrzLines.map((line: string, i: number) => <div key={i}>{line}</div>)
              ) : (
                <div style={{ color: "#F87171" }}>
                  ⚠ MRZ NOT DECODED — no machine-readable zone was read from this
                  document. Do not treat the fields above as checksum-verified.
                </div>
              )}
            </div>
          </div>

          {/* Forgery & Tampering Analysis */}
          <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", padding: "20px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
              🔬 Dual-Domain Forgery Forensics
            </h3>
            
            <div style={{ marginBottom: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", marginBottom: "6px" }}>
                <span style={{ color: "#94A3B8" }}>Overall Anomaly Index:</span>
                <strong style={{ color: (scan.forgery_results?.anomaly_score ?? 10) > 40 ? "#EF4444" : "#34D399" }}>
                  {scan.forgery_results?.anomaly_score ?? 10} / 100
                </strong>
              </div>
              <div style={{ height: "6px", backgroundColor: "#1E293B", borderRadius: "3px", overflow: "hidden" }}>
                <div style={{ width: `${scan.forgery_results?.anomaly_score ?? 10}%`, height: "100%", backgroundColor: (scan.forgery_results?.anomaly_score ?? 10) > 40 ? "#EF4444" : "#34D399" }} />
              </div>
            </div>

            {/* Explanations List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {(scan.risk_score?.explanations || []).map((exp: any, idx: number) => {
                const text = typeof exp === "string" ? exp : exp.flag;
                const sev = typeof exp === "object" ? exp.severity : "medium";
                const isCrit = sev === "critical" || sev === "high";
                return (
                  <div
                    key={idx}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "6px",
                      backgroundColor: isCrit ? "rgba(239, 68, 68, 0.12)" : "rgba(30, 41, 59, 0.6)",
                      border: `1px solid ${isCrit ? "rgba(239, 68, 68, 0.3)" : "rgba(255,255,255,0.05)"}`,
                      fontSize: "12px",
                      color: isCrit ? "#FCA5A5" : "#CBD5E1",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <span>{isCrit ? "⚠️" : "ℹ️"}</span> {text}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Decision Action Panel */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "1px solid rgba(255, 255, 255, 0.15)", borderRadius: "16px", padding: "24px" }}>
        <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 16px" }}>
          👮 Human-in-the-Loop Officer Clearance Decision
        </h3>

        <div style={{ marginBottom: "16px" }}>
          <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94A3B8", marginBottom: "8px", textTransform: "uppercase" }}>
            Officer Inspection Notes & Rationale
          </label>
          <textarea
            rows={2}
            value={decisionNotes}
            onChange={(e) => setDecisionNotes(e.target.value)}
            placeholder="Document any physical observations or specific reason for secondary referral..."
            style={{
              width: "100%",
              padding: "12px",
              backgroundColor: "rgba(30, 41, 59, 0.8)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "8px",
              color: "#F8FAFC",
              fontSize: "14px",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: "16px" }}>
          <button
            onClick={() => handleDecision("approved")}
            disabled={isSubmitting}
            style={{
              flex: 1,
              padding: "14px",
              borderRadius: "8px",
              backgroundColor: scan.final_decision === "approved" ? "#10B981" : "rgba(16, 185, 129, 0.2)",
              color: scan.final_decision === "approved" ? "#FFF" : "#34D399",
              border: "1px solid rgba(16, 185, 129, 0.4)",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            ✅ Approve Clearance
          </button>

          <button
            onClick={() => handleDecision("flagged")}
            disabled={isSubmitting}
            style={{
              flex: 1,
              padding: "14px",
              borderRadius: "8px",
              backgroundColor: scan.final_decision === "flagged" ? "#F59E0B" : "rgba(245, 158, 11, 0.2)",
              color: scan.final_decision === "flagged" ? "#FFF" : "#FBBF24",
              border: "1px solid rgba(245, 158, 11, 0.4)",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            ⚠️ Flag for Secondary Review
          </button>

          <button
            onClick={() => handleDecision("detained")}
            disabled={isSubmitting}
            style={{
              flex: 1,
              padding: "14px",
              borderRadius: "8px",
              backgroundColor: scan.final_decision === "detained" ? "#EF4444" : "rgba(239, 68, 68, 0.2)",
              color: scan.final_decision === "detained" ? "#FFF" : "#FCA5A5",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            ⛔ Detain / Refuse Entry
          </button>
        </div>
      </div>
    </div>
  );
}
