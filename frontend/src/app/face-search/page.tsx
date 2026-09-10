"use client";

/**
 * Biometric Identification console.
 *
 * Two modes:
 *   1:N  identify one face against every stored encounter
 *   1:1  compare two images directly
 *
 * Every number shown is the raw SFace cosine similarity. Nothing is rescaled.
 * A "NOT COMPARABLE" verdict means no usable face was found, or several were —
 * it is deliberately distinct from "these are different people".
 */

import React, { useEffect, useRef, useState } from "react";
import { faceApi } from "@/lib/api";
import type {
  FaceCompareResponse,
  FaceGalleryHealth,
  FaceSearchResponse,
} from "@/types";

const PANEL: React.CSSProperties = {
  backgroundColor: "rgba(15, 23, 42, 0.6)",
  border: "1px solid rgba(255, 255, 255, 0.08)",
  borderRadius: "12px",
  padding: "20px",
  marginBottom: "20px",
};

const LABEL: React.CSSProperties = {
  fontSize: "11px",
  color: "#64748B",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  display: "block",
  marginBottom: "6px",
};

function cosineColour(cos: number, threshold: number): string {
  if (cos >= threshold) return "#34D399";
  if (cos >= threshold * 0.7) return "#FBBF24";
  return "#94A3B8";
}

/** File picker with an inline preview. */
function ImagePicker({
  label,
  file,
  onPick,
}: {
  label: string;
  file: File | null;
  onPick: (f: File | null) => void;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    // Revoke on cleanup so repeated picks do not leak blob URLs.
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div>
      <span style={LABEL}>{label}</span>
      <div
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label={`Choose ${label}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        style={{
          width: "100%",
          height: "200px",
          backgroundColor: "#0B0F19",
          border: "1px dashed rgba(255,255,255,0.18)",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          overflow: "hidden",
        }}
      >
        {preview ? (
          <img
            src={preview}
            alt={`${label} preview`}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        ) : (
          <span style={{ color: "#64748B", fontSize: "13px" }}>
            Click to choose an image
          </span>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/bmp"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        style={{ display: "none" }}
      />
      {file && (
        <p style={{ fontSize: "11px", color: "#94A3B8", margin: "6px 0 0" }}>
          {file.name} ({(file.size / 1024).toFixed(0)} KB)
        </p>
      )}
    </div>
  );
}

export default function FaceSearchPage() {
  const [mode, setMode] = useState<"search" | "compare">("search");

  const [probe, setProbe] = useState<File | null>(null);
  const [imageA, setImageA] = useState<File | null>(null);
  const [imageB, setImageB] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<FaceSearchResponse | null>(null);
  const [compareResult, setCompareResult] = useState<FaceCompareResponse | null>(null);
  const [gallery, setGallery] = useState<FaceGalleryHealth | null>(null);

  useEffect(() => {
    faceApi.galleryHealth().then(setGallery).catch(() => setGallery(null));
  }, []);

  async function runSearch() {
    if (!probe) {
      setError("Choose a probe image first.");
      return;
    }
    setBusy(true);
    setError(null);
    setSearchResult(null);
    try {
      setSearchResult(await faceApi.search(probe, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setBusy(false);
    }
  }

  async function runCompare() {
    if (!imageA || !imageB) {
      setError("Choose both images first.");
      return;
    }
    setBusy(true);
    setError(null);
    setCompareResult(null);
    try {
      setCompareResult(await faceApi.compare(imageA, imageB));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", paddingBottom: "60px" }}>
      <h1 style={{ fontSize: "22px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 4px" }}>
        Biometric Identification
      </h1>
      <p style={{ fontSize: "13px", color: "#94A3B8", margin: "0 0 20px" }}>
        SFace 128-d embeddings, YuNet detection. Scores are raw cosine
        similarity — not rescaled, not a confidence percentage.
      </p>

      {gallery && (
        <div style={{ ...PANEL, padding: "12px 16px", fontSize: "12px", color: "#94A3B8" }}>
          Gallery: <strong style={{ color: "#F8FAFC" }}>{gallery.comparable}</strong>{" "}
          comparable embedding(s) of {gallery.total_with_embedding} stored.
          {gallery.incomparable > 0 && (
            <span style={{ color: "#FBBF24" }}>
              {" "}
              {gallery.incomparable} record(s) hold embeddings of the wrong
              dimensionality and are excluded from every search.
            </span>
          )}
        </div>
      )}

      {/* Mode switch */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px" }}>
        {(
          [
            ["search", "1:N — Identify against database"],
            ["compare", "1:1 — Compare two images"],
          ] as const
        ).map(([key, text]) => (
          <button
            key={key}
            onClick={() => {
              setMode(key);
              setError(null);
            }}
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              border:
                mode === key
                  ? "1px solid rgba(56, 189, 248, 0.5)"
                  : "1px solid rgba(255,255,255,0.1)",
              backgroundColor: mode === key ? "rgba(56, 189, 248, 0.15)" : "transparent",
              color: mode === key ? "#38BDF8" : "#94A3B8",
            }}
          >
            {text}
          </button>
        ))}
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

      {/* ── 1:N ────────────────────────────────────────────────────────── */}
      {mode === "search" && (
        <>
          <div style={PANEL}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
              Probe face
            </h3>
            <p style={{ fontSize: "12px", color: "#94A3B8", margin: "0 0 12px" }}>
              For a traveller presenting no document, the face itself is the
              query. It is matched against every stored encounter.
            </p>
            <div style={{ maxWidth: "320px" }}>
              <ImagePicker label="Face to identify" file={probe} onPick={setProbe} />
            </div>
            <button
              onClick={runSearch}
              disabled={busy || !probe}
              style={{
                marginTop: "16px",
                padding: "10px 20px",
                borderRadius: "8px",
                border: "1px solid rgba(56, 189, 248, 0.4)",
                backgroundColor: busy || !probe ? "rgba(56,189,248,0.08)" : "rgba(56, 189, 248, 0.2)",
                color: "#38BDF8",
                fontSize: "13px",
                fontWeight: 600,
                cursor: busy || !probe ? "not-allowed" : "pointer",
              }}
            >
              {busy ? "Searching…" : "Run 1:N search"}
            </button>
          </div>

          {searchResult && (
            <div style={PANEL}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "12px" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: 0 }}>
                  Result
                </h3>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    color: searchResult.identified ? "#EF4444" : "#34D399",
                  }}
                >
                  {searchResult.identified
                    ? `${searchResult.match_count} MATCH(ES) FOUND`
                    : "NO MATCH IN DATABASE"}
                </span>
              </div>

              <div style={{ fontSize: "12px", color: "#94A3B8", marginBottom: "16px", lineHeight: 1.7 }}>
                Compared against {searchResult.compared} of {searchResult.gallery_size} stored
                record(s). Threshold: raw cosine ≥{" "}
                <strong style={{ color: "#F8FAFC" }}>{searchResult.threshold}</strong>. Detector
                confidence on probe: {searchResult.probe.detector_confidence ?? "n/a"}.
                {searchResult.incomparable_records > 0 && (
                  <>
                    {" "}
                    <span style={{ color: "#FBBF24" }}>
                      {searchResult.incomparable_records} record(s) skipped as incomparable.
                    </span>
                  </>
                )}
              </div>

              {searchResult.results.length === 0 ? (
                <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0 }}>
                  No comparable records in the gallery yet.
                </p>
              ) : (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                    <caption style={{ captionSide: "top", textAlign: "left", color: "#64748B", fontSize: "11px", paddingBottom: "8px" }}>
                      Candidates ranked by raw cosine similarity, highest first
                    </caption>
                    <thead>
                      <tr style={{ color: "#64748B", textAlign: "left" }}>
                        <th scope="col" style={{ padding: "8px 10px" }}>#</th>
                        <th scope="col" style={{ padding: "8px 10px" }}>Name on record</th>
                        <th scope="col" style={{ padding: "8px 10px" }}>Document</th>
                        <th scope="col" style={{ padding: "8px 10px" }}>Encounter</th>
                        <th scope="col" style={{ padding: "8px 10px" }}>Cosine</th>
                        <th scope="col" style={{ padding: "8px 10px" }}>Verdict</th>
                      </tr>
                    </thead>
                    <tbody>
                      {searchResult.results.map((m, i) => (
                        <tr key={m.scan_id} style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                          <td style={{ padding: "10px", color: "#64748B" }}>{i + 1}</td>
                          <td style={{ padding: "10px", color: "#F8FAFC", fontWeight: 600 }}>
                            {m.holder_name || "NOT READ"}
                          </td>
                          <td style={{ padding: "10px", color: "#94A3B8", fontFamily: "monospace" }}>
                            {m.document_number || "—"}
                          </td>
                          <td style={{ padding: "10px", color: "#94A3B8" }}>
                            {m.encounter_date ? new Date(m.encounter_date).toLocaleDateString() : "—"}
                          </td>
                          <td
                            style={{
                              padding: "10px",
                              fontWeight: 700,
                              fontFamily: "monospace",
                              color: cosineColour(m.cosine_similarity, searchResult.threshold),
                            }}
                          >
                            {m.cosine_similarity.toFixed(4)}
                          </td>
                          <td style={{ padding: "10px", fontWeight: 700, color: m.is_match ? "#EF4444" : "#64748B" }}>
                            {m.is_match ? "SAME PERSON" : "different"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── 1:1 ────────────────────────────────────────────────────────── */}
      {mode === "compare" && (
        <>
          <div style={PANEL}>
            <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
              Compare two faces
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
              <ImagePicker label="Image A" file={imageA} onPick={setImageA} />
              <ImagePicker label="Image B" file={imageB} onPick={setImageB} />
            </div>
            <button
              onClick={runCompare}
              disabled={busy || !imageA || !imageB}
              style={{
                marginTop: "16px",
                padding: "10px 20px",
                borderRadius: "8px",
                border: "1px solid rgba(56, 189, 248, 0.4)",
                backgroundColor:
                  busy || !imageA || !imageB ? "rgba(56,189,248,0.08)" : "rgba(56, 189, 248, 0.2)",
                color: "#38BDF8",
                fontSize: "13px",
                fontWeight: 600,
                cursor: busy || !imageA || !imageB ? "not-allowed" : "pointer",
              }}
            >
              {busy ? "Comparing…" : "Compare"}
            </button>
          </div>

          {compareResult && (
            <div style={PANEL}>
              <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#F8FAFC", margin: "0 0 16px" }}>
                Result
              </h3>

              {compareResult.verdict === "NOT_COMPARABLE" ? (
                <div style={{ fontSize: "13px", color: "#FBBF24", lineHeight: 1.7 }}>
                  <strong>NOT COMPARABLE</strong> — no similarity was measured.
                  This is not a mismatch; the images could not be used.
                  <ul style={{ margin: "10px 0 0", paddingLeft: "20px", color: "#94A3B8" }}>
                    <li>
                      Image A: {compareResult.image_a.face_count} face(s) detected
                      {compareResult.image_a.reason ? ` — ${compareResult.image_a.reason}` : ""}
                    </li>
                    <li>
                      Image B: {compareResult.image_b.face_count} face(s) detected
                      {compareResult.image_b.reason ? ` — ${compareResult.image_b.reason}` : ""}
                    </li>
                  </ul>
                </div>
              ) : (
                <>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: "12px",
                      marginBottom: "12px",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "34px",
                        fontWeight: 700,
                        fontFamily: "monospace",
                        color: compareResult.is_match ? "#34D399" : "#EF4444",
                      }}
                    >
                      {compareResult.cosine_similarity?.toFixed(4)}
                    </span>
                    <span
                      style={{
                        fontSize: "14px",
                        fontWeight: 700,
                        color: compareResult.is_match ? "#34D399" : "#EF4444",
                      }}
                    >
                      {compareResult.verdict === "SAME_PERSON" ? "SAME PERSON" : "DIFFERENT PERSON"}
                    </span>
                  </div>
                  <p style={{ fontSize: "12px", color: "#94A3B8", margin: 0, lineHeight: 1.7 }}>
                    Raw cosine similarity against a threshold of{" "}
                    <strong style={{ color: "#F8FAFC" }}>{compareResult.threshold}</strong> (SFace
                    operating point). Detector confidence — A:{" "}
                    {compareResult.image_a.confidence ?? "n/a"}, B:{" "}
                    {compareResult.image_b.confidence ?? "n/a"}.
                  </p>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
