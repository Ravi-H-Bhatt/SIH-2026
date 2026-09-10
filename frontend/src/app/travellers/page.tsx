"use client";

/**
 * Travellers gallery — every screened traveller with their document scan and
 * live face capture side by side.
 *
 * Images arrive as short-lived Supabase signed URLs minted per request. They are
 * never public objects, so a URL that has expired simply fails to load rather
 * than exposing anything.
 *
 * Fields that were never read render as "NOT READ" rather than falling back to
 * plausible sample values.
 */

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { scansApi } from "@/lib/api";
import type { ScanRecord } from "@/types";

const PAGE_SIZE = 12;

const RISK_COLOURS: Record<string, string> = {
  low: "#34D399",
  medium: "#FBBF24",
  high: "#FCA5A5",
  critical: "#EF4444",
};

function riskColour(level?: string | null): string {
  return RISK_COLOURS[String(level || "low").toLowerCase()] || "#94A3B8";
}

/** Signed-URL image with a graceful fallback when absent or expired. */
function Thumb({
  url,
  alt,
  label,
}: {
  url?: string | null;
  alt: string;
  label: string;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <span
        style={{
          fontSize: "10px",
          color: "#64748B",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          display: "block",
          marginBottom: "4px",
        }}
      >
        {label}
      </span>
      <div
        style={{
          width: "100%",
          height: "130px",
          backgroundColor: "#0B0F19",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "6px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {url && !failed ? (
          <img
            src={url}
            alt={alt}
            onError={() => setFailed(true)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <span style={{ fontSize: "11px", color: "#64748B", textAlign: "center", padding: "0 8px" }}>
            {url ? "Image unavailable" : "Not captured"}
          </span>
        )}
      </div>
    </div>
  );
}

export default function TravellersPage() {
  const [scans, setScans] = useState<ScanRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await scansApi.getTravellers({
        page,
        page_size: PAGE_SIZE,
        search: search.trim() || undefined,
        risk_level: riskFilter || undefined,
      });
      setScans(res.scans || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load travellers.");
      setScans([]);
    } finally {
      setLoading(false);
    }
  }, [page, search, riskFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div style={{ maxWidth: "1240px", margin: "0 auto", paddingBottom: "60px" }}>
      <h1 style={{ fontSize: "22px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 4px" }}>
        Travellers
      </h1>
      <p style={{ fontSize: "13px", color: "#94A3B8", margin: "0 0 20px" }}>
        Every screened traveller with their document scan and live capture.
        {total > 0 && ` ${total} record(s).`}
      </p>

      {/* Filters */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px", flexWrap: "wrap" }}>
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search name or document number…"
          aria-label="Search travellers by name or document number"
          style={{
            flex: "1 1 260px",
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.1)",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            color: "#F8FAFC",
            fontSize: "13px",
          }}
        />
        <select
          value={riskFilter}
          onChange={(e) => {
            setRiskFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by risk level"
          style={{
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.1)",
            backgroundColor: "rgba(15, 23, 42, 0.6)",
            color: "#F8FAFC",
            fontSize: "13px",
          }}
        >
          <option value="">All risk levels</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
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
            marginBottom: "20px",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <p style={{ color: "#94A3B8", fontSize: "13px" }}>Loading travellers…</p>
      ) : scans.length === 0 ? (
        <p style={{ color: "#94A3B8", fontSize: "13px" }}>
          No travellers match this filter.
        </p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "16px",
          }}
        >
          {scans.map((scan) => {
            const level = scan.risk_score?.risk_level || scan.risk_score?.level;
            const face = scan.face_result ?? scan.face_results;
            const cosine = face?.match_score ?? face?.similarity_score;

            return (
              <div
                key={scan.id}
                style={{
                  backgroundColor: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "12px",
                  padding: "16px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "12px",
                    gap: "8px",
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <p
                      style={{
                        color: scan.holder_name ? "#F8FAFC" : "#F87171",
                        fontWeight: 600,
                        fontSize: "14px",
                        margin: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {scan.holder_name || "⚠ NOT READ"}
                    </p>
                    <p
                      style={{
                        color: "#94A3B8",
                        fontSize: "11px",
                        margin: "2px 0 0",
                        fontFamily: "monospace",
                      }}
                    >
                      {scan.document_number || "—"} · {scan.document_type || "—"}
                    </p>
                  </div>
                  {level && (
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 700,
                        color: riskColour(level),
                        border: `1px solid ${riskColour(level)}55`,
                        borderRadius: "4px",
                        padding: "3px 6px",
                        textTransform: "uppercase",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {level}
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", gap: "10px", marginBottom: "12px" }}>
                  <Thumb url={scan.document_image_url} alt="Document scan" label="Document" />
                  <Thumb url={scan.face_image_url} alt="Live face capture" label="Live face" />
                </div>

                <div style={{ fontSize: "11px", color: "#94A3B8", lineHeight: 1.8 }}>
                  <div>
                    Nationality: {scan.issuing_country || "NOT READ"}
                  </div>
                  <div>
                    Face match:{" "}
                    {cosine === null || cosine === undefined ? (
                      <span style={{ color: "#94A3B8" }}>not performed</span>
                    ) : (
                      <span
                        style={{
                          color: cosine >= 0.363 ? "#34D399" : "#EF4444",
                          fontFamily: "monospace",
                          fontWeight: 600,
                        }}
                      >
                        {cosine.toFixed(4)} {cosine >= 0.363 ? "MATCH" : "NO MATCH"}
                      </span>
                    )}
                  </div>
                  <div>
                    Screened:{" "}
                    {scan.created_at ? new Date(scan.created_at).toLocaleString() : "—"}
                  </div>
                </div>

                <Link
                  href={`/scans/${scan.id}`}
                  style={{
                    display: "inline-block",
                    marginTop: "12px",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#38BDF8",
                    textDecoration: "none",
                  }}
                >
                  View full evidence →
                </Link>
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div
          style={{
            display: "flex",
            gap: "10px",
            alignItems: "center",
            justifyContent: "center",
            marginTop: "24px",
          }}
        >
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              padding: "8px 14px",
              borderRadius: "6px",
              border: "1px solid rgba(255,255,255,0.1)",
              backgroundColor: "transparent",
              color: page <= 1 ? "#475569" : "#94A3B8",
              fontSize: "12px",
              cursor: page <= 1 ? "not-allowed" : "pointer",
            }}
          >
            ← Previous
          </button>
          <span style={{ fontSize: "12px", color: "#94A3B8" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            style={{
              padding: "8px 14px",
              borderRadius: "6px",
              border: "1px solid rgba(255,255,255,0.1)",
              backgroundColor: "transparent",
              color: page >= totalPages ? "#475569" : "#94A3B8",
              fontSize: "12px",
              cursor: page >= totalPages ? "not-allowed" : "pointer",
            }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
