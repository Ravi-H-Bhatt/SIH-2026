"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { scansApi } from "@/lib/api";
import CameraCaptureModal from "@/components/CameraCaptureModal";

export default function DocumentScannerPage() {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);
  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [facePreview, setFacePreview] = useState<string | null>(null);
  const [docType, setDocType] = useState<string>("passport");
  const [issuingCountry, setIssuingCountry] = useState<string>("IND");
  const [isScanning, setIsScanning] = useState(false);
  const [scanStep, setScanStep] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const [cameraModalOpen, setCameraModalOpen] = useState(false);
  const [cameraMode, setCameraMode] = useState<"document" | "face">("document");
  const docInputRef = useRef<HTMLInputElement>(null);
  const faceInputRef = useRef<HTMLInputElement>(null);

  const handleDocChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setDocFile(file);
      setDocPreview(URL.createObjectURL(file));
    }
  };

  const handleFaceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setFaceFile(file);
      setFacePreview(URL.createObjectURL(file));
    }
  };

  const handleCameraCapture = (file: File, previewUrl: string) => {
    if (cameraMode === "document") {
      setDocFile(file);
      setDocPreview(previewUrl);
    } else {
      setFaceFile(file);
      setFacePreview(previewUrl);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile) {
      setError("Please select or capture a document image first.");
      return;
    }

    setError(null);
    setIsScanning(true);

    try {
      setScanStep("Uploading & Preprocessing Image...");
      await new Promise((r) => setTimeout(r, 600));

      setScanStep("Running OCR & Extracting ICAO MRZ Lines...");
      await new Promise((r) => setTimeout(r, 800));

      setScanStep("Analyzing Forgery & Document Tampering...");
      await new Promise((r) => setTimeout(r, 800));

      setScanStep("Computing Biometric Matching & Risk Assessment...");
      
      const formData = new FormData();
      formData.append("document_image", docFile);
      if (faceFile) {
        formData.append("face_image", faceFile);
      }
      formData.append("document_type", docType);
      formData.append("issuing_country", issuingCountry);

      const result = await scansApi.uploadScan(formData);
      router.push(`/scans/${result.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to complete analysis. Please try again.");
      setIsScanning(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#070A12" }}>
      {/* Professional Header */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", backgroundColor: "rgba(15,23,42,0.5)" }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }}>
            <div style={{
              width: "40px", height: "40px", borderRadius: "10px",
              background: "linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "24px"
            }}>
              📋
            </div>
            <div>
              <h1 style={{ fontSize: "28px", fontWeight: 800, margin: "0", color: "#F8FAFC", letterSpacing: "-0.5px" }}>
                Document Verification Station
              </h1>
              <p style={{ fontSize: "14px", color: "#94A3B8", margin: "4px 0 0", fontWeight: 500 }}>
                AI-powered screening: OCR, forgery detection, biometric matching
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 24px" }}>
        {error && (
          <div style={{
            backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#FCA5A5", padding: "16px 20px", borderRadius: "12px", marginBottom: "32px",
            fontSize: "14px", fontWeight: 500
          }}>
            ⚠ {error}
          </div>
        )}

        {isScanning ? (
          /* Processing Screen */
          <div style={{
            backgroundColor: "rgba(15, 23, 42, 0.8)", border: "1px solid rgba(59, 130, 246, 0.3)",
            borderRadius: "16px", padding: "80px 40px", textAlign: "center"
          }}>
            <div style={{
              width: "64px", height: "64px", border: "4px solid rgba(59, 130, 246, 0.2)",
              borderTopColor: "#3B82F6", borderRadius: "50%",
              animation: "spin 1s linear infinite", margin: "0 auto 32px"
            }} />
            <h2 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", marginBottom: "12px" }}>
              Analyzing Document...
            </h2>
            <p style={{ fontSize: "16px", color: "#3B82F6", fontWeight: 600, margin: 0 }}>
              {scanStep}
            </p>
            <div style={{ marginTop: "24px", fontSize: "13px", color: "#64748B" }}>
              Please wait • Document integrity and biometric verification in progress
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {/* Metadata Section */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px",
              backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "16px", padding: "28px", marginBottom: "32px"
            }}>
              <div>
                <label style={{
                  display: "block", fontSize: "12px", fontWeight: 700, color: "#CBD5E1",
                  marginBottom: "10px", textTransform: "uppercase", letterSpacing: "0.5px"
                }}>
                  Document Type
                </label>
                <select value={docType} onChange={(e) => setDocType(e.target.value)} style={{
                  width: "100%", padding: "12px 14px", backgroundColor: "rgba(30, 41, 59, 0.8)",
                  border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "8px", color: "#F8FAFC",
                  fontSize: "14px", fontWeight: 500, outline: "none"
                }}>
                  <option value="passport">Passport (ICAO 9303)</option>
                  <option value="visa">Visa / Travel Permit</option>
                  <option value="id_card">National ID Card</option>
                  <option value="travel_document">Travel Document</option>
                </select>
              </div>

              <div>
                <label style={{
                  display: "block", fontSize: "12px", fontWeight: 700, color: "#CBD5E1",
                  marginBottom: "10px", textTransform: "uppercase", letterSpacing: "0.5px"
                }}>
                  Issuing Country (ISO-3 Code)
                </label>
                <input type="text" value={issuingCountry} onChange={(e) => setIssuingCountry(e.target.value.toUpperCase())}
                  placeholder="IND" maxLength={3} style={{
                    width: "100%", padding: "12px 14px", backgroundColor: "rgba(30, 41, 59, 0.8)",
                    border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "8px", color: "#F8FAFC",
                    fontSize: "14px", fontWeight: 500, outline: "none", boxSizing: "border-box"
                  }} />
              </div>
            </div>

            {/* Upload Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "28px", marginBottom: "32px" }}>
              {/* Document Card */}
              <div style={{
                backgroundColor: "rgba(15, 23, 42, 0.6)", border: "2px solid rgba(59, 130, 246, 0.3)",
                borderRadius: "16px", padding: "28px", display: "flex", flexDirection: "column"
              }}>
                <div style={{ marginBottom: "20px" }}>
                  <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 8px", letterSpacing: "-0.5px" }}>
                    Primary Document
                  </h3>
                  <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0, lineHeight: "1.5" }}>
                    Passport or travel document with MRZ barcode visible
                  </p>
                </div>

                {docPreview ? (
                  <div style={{
                    position: "relative", height: "200px", borderRadius: "12px", overflow: "hidden",
                    border: "1px solid rgba(255,255,255,0.1)", marginBottom: "16px"
                  }}>
                    <img src={docPreview} alt="Document" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                    <div style={{
                      position: "absolute", top: "10px", right: "10px", backgroundColor: "#10B981",
                      color: "#FFF", fontSize: "12px", fontWeight: 700, padding: "4px 12px", borderRadius: "14px"
                    }}>
                      Ready
                    </div>
                  </div>
                ) : (
                  <div style={{
                    height: "180px", borderRadius: "12px", backgroundColor: "rgba(59, 130, 246, 0.08)",
                    border: "1px dashed rgba(59, 130, 246, 0.4)", display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", marginBottom: "16px"
                  }}>
                    <div style={{ fontSize: "48px", marginBottom: "10px" }}>📄</div>
                    <span style={{ fontSize: "13px", color: "#64748B", fontWeight: 500 }}>Click below to upload</span>
                  </div>
                )}

                <div style={{ display: "flex", gap: "8px" }}>
                  <button type="button" onClick={() => {
                    setCameraMode("document");
                    setCameraModalOpen(true);
                  }} style={{
                    flex: 1, padding: "11px", borderRadius: "8px",
                    background: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
                    border: "none", color: "#FFF", fontSize: "13px", fontWeight: 600,
                    cursor: "pointer", boxShadow: "0 2px 8px rgba(59, 130, 246, 0.3)"
                  }}>
                    Camera
                  </button>
                  <button type="button" onClick={() => docInputRef.current?.click()} style={{
                    flex: 1, padding: "11px", borderRadius: "8px", backgroundColor: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.15)", color: "#E2E8F0", fontSize: "13px",
                    fontWeight: 600, cursor: "pointer"
                  }}>
                    Upload
                  </button>
                  <input ref={docInputRef} type="file" accept="image/*" onChange={handleDocChange} style={{ display: "none" }} />
                </div>
              </div>

              {/* Face Card */}
              <div style={{
                backgroundColor: "rgba(15, 23, 42, 0.6)", border: "2px solid rgba(16, 185, 129, 0.3)",
                borderRadius: "16px", padding: "28px", display: "flex", flexDirection: "column"
              }}>
                <div style={{ marginBottom: "20px" }}>
                  <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 8px", letterSpacing: "-0.5px" }}>
                    Live Face Capture
                  </h3>
                  <p style={{ fontSize: "13px", color: "#94A3B8", margin: 0, lineHeight: "1.5" }}>
                    Biometric verification and liveness check
                  </p>
                </div>

                {facePreview ? (
                  <div style={{
                    position: "relative", height: "200px", borderRadius: "12px", overflow: "hidden",
                    border: "1px solid rgba(255,255,255,0.1)", marginBottom: "16px"
                  }}>
                    <img src={facePreview} alt="Face" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                    <div style={{
                      position: "absolute", top: "10px", right: "10px", backgroundColor: "#10B981",
                      color: "#FFF", fontSize: "12px", fontWeight: 700, padding: "4px 12px", borderRadius: "14px"
                    }}>
                      Ready
                    </div>
                  </div>
                ) : (
                  <div style={{
                    height: "180px", borderRadius: "12px", backgroundColor: "rgba(16, 185, 129, 0.08)",
                    border: "1px dashed rgba(16, 185, 129, 0.4)", display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", marginBottom: "16px"
                  }}>
                    <div style={{ fontSize: "48px", marginBottom: "10px" }}>👤</div>
                    <span style={{ fontSize: "13px", color: "#64748B", fontWeight: 500 }}>Click below to upload</span>
                  </div>
                )}

                <div style={{ display: "flex", gap: "8px" }}>
                  <button type="button" onClick={() => {
                    setCameraMode("face");
                    setCameraModalOpen(true);
                  }} style={{
                    flex: 1, padding: "11px", borderRadius: "8px",
                    background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                    border: "none", color: "#FFF", fontSize: "13px", fontWeight: 600,
                    cursor: "pointer", boxShadow: "0 2px 8px rgba(16, 185, 129, 0.3)"
                  }}>
                    Camera
                  </button>
                  <button type="button" onClick={() => faceInputRef.current?.click()} style={{
                    flex: 1, padding: "11px", borderRadius: "8px", backgroundColor: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.15)", color: "#E2E8F0", fontSize: "13px",
                    fontWeight: 600, cursor: "pointer"
                  }}>
                    Upload
                  </button>
                  <input ref={faceInputRef} type="file" accept="image/*" onChange={handleFaceChange} style={{ display: "none" }} />
                </div>
              </div>
            </div>

            {/* Submit Button */}
            <button type="submit" disabled={!docFile} style={{
              width: "100%", padding: "16px 24px", borderRadius: "12px",
              background: docFile ? "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)" : "rgba(30, 41, 59, 0.5)",
              color: docFile ? "#FFF" : "#64748B", fontWeight: 700, fontSize: "16px",
              border: "none", cursor: docFile ? "pointer" : "not-allowed",
              boxShadow: docFile ? "0 4px 20px rgba(59, 130, 246, 0.4)" : "none",
              transition: "all 0.2s ease"
            }}>
              Analyze Document & Biometrics
            </button>
          </form>
        )}
      </div>

      {/* Camera Modal */}
      <CameraCaptureModal isOpen={cameraModalOpen} onClose={() => setCameraModalOpen(false)}
        onCapture={handleCameraCapture} mode={cameraMode} />

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

