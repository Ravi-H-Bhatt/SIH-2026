"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { scansApi } from "@/lib/api";
import CameraCaptureModal from "@/components/CameraCaptureModal";
import { Button } from "@/components/ui/Button";

type KioskStep = "welcome" | "scan_passport" | "face_capture" | "processing" | "result";

export default function KioskPage() {
  const [step, setStep] = useState<KioskStep>("welcome");
  const [language, setLanguage] = useState<string>("EN");

  // Document & Face File state
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docPreview, setDocPreview] = useState<string | null>(null);

  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [facePreview, setFacePreview] = useState<string | null>(null);

  // Processing & Result State
  const [processingStage, setProcessingStage] = useState<string>("Reading Document...");
  const [scanResult, setScanResult] = useState<any>(null);
  const [isError, setIsError] = useState<boolean>(false);
  // The real backend message. Without this the kiosk showed a generic
  // "SYSTEM ERROR" for everything, which made failures impossible to diagnose.
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const docInputRef = useRef<HTMLInputElement>(null);
  const faceInputRef = useRef<HTMLInputElement>(null);

  // WebRTC Camera State
  const [docCameraOpen, setDocCameraOpen] = useState(false);
  const kioskVideoRef = useRef<HTMLVideoElement | null>(null);
  const kioskCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [kioskStream, setKioskStream] = useState<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState<boolean>(false);
  const [kioskCameraError, setKioskCameraError] = useState<string | null>(null);

  // Start live camera stream automatically when entering face_capture step
  useEffect(() => {
    let activeStream: MediaStream | null = null;
    if (step === "face_capture" && !facePreview) {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices
          .getUserMedia({
            video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false,
          })
          .then((mediaStream) => {
            activeStream = mediaStream;
            setKioskStream(mediaStream);
            setCameraActive(true);
            setKioskCameraError(null);
            if (kioskVideoRef.current) {
              kioskVideoRef.current.srcObject = mediaStream;
            }
          })
          .catch((err) => {
            console.warn("[Kiosk Camera] Could not access live camera:", err);
            setKioskCameraError("Webcam not accessible or permission denied. Please select or upload a photo.");
            setCameraActive(false);
          });
      } else {
        setKioskCameraError("Live camera is not supported in this browser environment.");
      }
    } else {
      if (kioskStream) {
        kioskStream.getTracks().forEach((t) => t.stop());
        setKioskStream(null);
        setCameraActive(false);
      }
    }

    return () => {
      if (activeStream) {
        activeStream.getTracks().forEach((t) => t.stop());
      }
    };
  }, [step, facePreview]);

  // Ensure video element receives stream when ref or stream updates
  useEffect(() => {
    if (kioskVideoRef.current && kioskStream && !facePreview) {
      kioskVideoRef.current.srcObject = kioskStream;
    }
  }, [kioskStream, facePreview]);

  // Snap photo from live stream
  const handleSnapKioskPhoto = () => {
    if (!kioskVideoRef.current) return;
    const video = kioskVideoRef.current;
    const canvas = kioskCanvasRef.current || document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Flip horizontal for natural mirror look
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
        const file = new File([blob], `kiosk_live_face_${Date.now()}.jpg`, { type: "image/jpeg" });
        setFaceFile(file);
        setFacePreview(dataUrl);

        if (kioskStream) {
          kioskStream.getTracks().forEach((t) => t.stop());
          setKioskStream(null);
          setCameraActive(false);
        }
      },
      "image/jpeg",
      0.95
    );
  };

  const handleRetakeKioskPhoto = () => {
    setFacePreview(null);
    setFaceFile(null);
  };

  const handleDocCameraCapture = (file: File, previewUrl: string) => {
    setDocFile(file);
    setDocPreview(previewUrl);
  };

  // Translations dictionary for kiosk
  const t = {
    EN: {
      welcomeTitle: "BORDER CONTROL KIOSK",
      welcomeSubtitle: "Self-Service Passport & Biometric Verification",
      startBtn: "Touch Here to Begin",
      step1: "1. Scan Passport",
      step2: "2. Look at Camera",
      step3: "3. Verification",
      placePassport: "Place your Passport face-down on the scanner",
      uploadPassportBtn: "📷 Choose Passport Photo",
      continueBtn: "Next Step ➔",
      lookCamera: "Look directly at the camera frame",
      takePhotoBtn: "📸 Take Live Photo / Upload",
      submitScanBtn: "Verify Identity ⚡",
      processingTitle: "Analyzing Documents & Biometrics...",
      clearedTitle: "CLEARANCE APPROVED",
      clearedDesc: "Your identity has been verified. Please proceed to Automatic Gate 04.",
      flaggedTitle: "PLEASE WAIT FOR ASSISTANT",
      flaggedDesc: "Please step forward to Border Officer Desk 02 for assistance.",
      resetBtn: "Done / Next Traveler",
    },
    HI: {
      welcomeTitle: "सीमा नियंत्रण कियोस्क",
      welcomeSubtitle: "स्व-सेवा पासपोर्ट और बायोमेट्रिक सत्यापन",
      startBtn: "शुरू करने के लिए यहां छुएं",
      step1: "1. पासपोर्ट स्कैन",
      step2: "2. कैमरा देखें",
      step3: "3. सत्यापन",
      placePassport: "अपना पासपोर्ट स्कैनर पर रखें",
      uploadPassportBtn: "📷 पासपोर्ट फोटो चुनें",
      continueBtn: "अगला कदम ➔",
      lookCamera: "कैमरा फ्रेम की ओर सीधे देखें",
      takePhotoBtn: "📸 फोटो खींचें / अपलोड करें",
      submitScanBtn: "सत्यापित करें ⚡",
      processingTitle: "दस्तावेजों और बायोमेट्रिक्स का विश्लेषण जारी...",
      clearedTitle: "सत्यापन स्वीकृत",
      clearedDesc: "आपकी पहचान सत्यापित हो गई है। ऑटोमैटिक गेट 04 पर जाएं।",
      flaggedTitle: "कृपया अधिकारी की प्रतीक्षा करें",
      flaggedDesc: "कृपया सहायता के लिए बॉर्डर ऑफिसर डेस्क 02 पर जाएं।",
      resetBtn: "अंतिम / अगला यात्री",
    },
  }[language as "EN" | "HI"] || {
    welcomeTitle: "BORDER CONTROL KIOSK",
    welcomeSubtitle: "Self-Service Passport & Biometric Verification",
    startBtn: "Touch Here to Begin",
    step1: "1. Scan Passport",
    step2: "2. Look at Camera",
    step3: "3. Verification",
    placePassport: "Place your Passport face-down on the scanner",
    uploadPassportBtn: "📷 Choose Passport Photo",
    continueBtn: "Next Step ➔",
    lookCamera: "Look directly at the camera frame",
    takePhotoBtn: "📸 Take Live Photo / Upload",
    submitScanBtn: "Verify Identity ⚡",
    processingTitle: "Analyzing Documents & Biometrics...",
    clearedTitle: "CLEARANCE APPROVED",
    clearedDesc: "Your identity has been verified. Please proceed to Automatic Gate 04.",
    flaggedTitle: "PLEASE WAIT FOR ASSISTANT",
    flaggedDesc: "Please step forward to Border Officer Desk 02 for assistance.",
    resetBtn: "Done / Next Traveler",
  };

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

  const handleStartProcessing = async () => {
    if (!docFile) {
      alert("Please upload or scan your passport image first.");
      return;
    }

    setStep("processing");
    setIsError(false);

    try {
      setProcessingStage("Extracting MRZ & Text Data...");
      await new Promise((r) => setTimeout(r, 600));

      setProcessingStage("Running Error Level & Forgery Detection...");
      await new Promise((r) => setTimeout(r, 600));

      setProcessingStage("Matching Facial Biometrics & Liveness...");
      await new Promise((r) => setTimeout(r, 600));

      setProcessingStage("Cross-Checking Watchlists & Risk Engine...");

      const formData = new FormData();
      formData.append("document_type", "passport");
      formData.append("checkpoint_id", "Kiosk-01 (Self Service)");
      formData.append("document_image", docFile);
      if (faceFile) {
        formData.append("face_image", faceFile);
      }

      const result = await scansApi.uploadScan(formData);
      setScanResult(result);
      setStep("result");
    } catch (err: any) {
      console.error("Scan processing error:", err);
      setIsError(true);
      // Never fabricate a clearance decision on failure — surface the cause.
      const raw = err?.message || String(err);
      setErrorMessage(
        raw === "Failed to fetch"
          ? "Cannot reach the screening server. Confirm the backend is running on " +
            (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "."
          : raw
      );
      setScanResult(null);
      setStep("result");
    }
  };

  const resetKiosk = () => {
    setStep("welcome");
    setDocFile(null);
    setDocPreview(null);
    setFaceFile(null);
    setFacePreview(null);
    setScanResult(null);
    setIsError(false);
    setErrorMessage(null);
  };

  const isApproved = scanResult && !isError && (
    scanResult.final_decision === "approved" ||
    (scanResult.risk_score && scanResult.risk_score.decision === "pass")
  );

  const getResultDisplay = () => {
    if (isError || !scanResult) {
      return {
        emoji: "🔴",
        title: "SCREENING COULD NOT COMPLETE",
        description:
          errorMessage ||
          "The screening service returned an error. Please see a border officer.",
        color: "#EF4444",
        bgColor: "rgba(239, 68, 68, 0.1)",
        borderColor: "#EF4444"
      };
    }

    const decision = scanResult.risk_score?.decision || scanResult.final_decision;
    const riskScore = scanResult.risk_score?.score || 0;
    const riskLevel = scanResult.risk_score?.risk_level || "unknown";

    if (decision === "pass" || decision === "PASS") {
      return {
        emoji: "✅",
        title: "VERIFICATION PASSED",
        description: `Risk Score: ${riskScore.toFixed(1)}/100 (${riskLevel}). Proceed to automated gate.`,
        color: "#10B981",
        bgColor: "rgba(16, 185, 129, 0.1)",
        borderColor: "#10B981"
      };
    } else if (decision === "review" || decision === "SECONDARY_REVIEW" || decision === "SECONDARY_HOLD") {
      return {
        emoji: "🟡",
        title: "SECONDARY REVIEW REQUIRED",
        description: `Risk Score: ${riskScore.toFixed(1)}/100 (${riskLevel}). Please proceed to Officer Station for verification.`,
        color: "#F59E0B",
        bgColor: "rgba(245, 158, 11, 0.1)",
        borderColor: "#F59E0B"
      };
    } else if (decision === "hold" || decision === "DETAIN" || decision === "detain") {
      return {
        emoji: "🔴",
        title: "DETAINED - OFFICER ASSISTANCE REQUIRED",
        description: `Risk Score: ${riskScore.toFixed(1)}/100 (${riskLevel}). Security alert - remain with officer.`,
        color: "#EF4444",
        bgColor: "rgba(239, 68, 68, 0.1)",
        borderColor: "#EF4444"
      };
    } else {
      return {
        emoji: "❓",
        title: "VERIFICATION STATUS UNKNOWN",
        description: "Unable to determine status. Please contact border officer.",
        color: "#94A3B8",
        bgColor: "rgba(148, 163, 184, 0.1)",
        borderColor: "#94A3B8"
      };
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#070A12",
        color: "#F8FAFC",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        fontFamily: "var(--font-sans, system-ui, -apple-system, sans-serif)",
        userSelect: "none",
      }}
    >
      {/* Kiosk Top Bar */}
      <header
        style={{
          padding: "20px 40px",
          backgroundColor: "#0F172A",
          borderBottom: "2px solid #1E293B",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "24px",
              boxShadow: "0 0 20px rgba(59, 130, 246, 0.5)",
            }}
          >
            🛡️
          </div>
          <div>
            <h1 style={{ fontSize: "20px", fontWeight: 800, margin: 0, letterSpacing: "-0.5px" }}>
              {t.welcomeTitle}
            </h1>
            <span style={{ fontSize: "12px", color: "#94A3B8", textTransform: "uppercase", letterSpacing: "1px" }}>
              Terminal 1 — Kiosk 01
            </span>
          </div>
        </div>

        {/* Language Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {["EN", "HI"].map((lang) => (
            <button
              key={lang}
              onClick={() => setLanguage(lang)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                backgroundColor: language === lang ? "#3B82F6" : "#1E293B",
                color: "#FFF",
                border: "1px solid #334155",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              {lang === "EN" ? "🇬🇧 English" : "🇮🇳 हिंदी"}
            </button>
          ))}
          <Link
            href="/"
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              color: "#FCA5A5",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              textDecoration: "none",
              fontSize: "13px",
              fontWeight: 600,
              marginLeft: "16px",
            }}
          >
            Exit Kiosk Mode ✖
          </Link>
        </div>
      </header>

      {/* Main Kiosk Content Area */}
      <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
        {/* Step 1: Welcome Screen */}
        {step === "welcome" && (
          <div style={{ textAlign: "center", maxWidth: "650px" }}>
            <div style={{ fontSize: "80px", marginBottom: "20px", filter: "drop-shadow(0 0 30px rgba(59, 130, 246, 0.5))" }}>
              🛂
            </div>
            <h2 style={{ fontSize: "36px", fontWeight: 800, marginBottom: "12px", letterSpacing: "-1px" }}>
              {t.welcomeTitle}
            </h2>
            <p style={{ fontSize: "18px", color: "#94A3B8", marginBottom: "40px", lineHeight: "1.5" }}>
              {t.welcomeSubtitle}
            </p>

            <Button size="kiosk" onClick={() => setStep("scan_passport")} className="px-10">
              {t.startBtn} <span aria-hidden="true">➔</span>
            </Button>
          </div>
        )}

        {/* Step 2: Scan Passport */}
        {step === "scan_passport" && (
          <div style={{ width: "100%", maxWidth: "720px", backgroundColor: "#0F172A", border: "2px solid #1E293B", borderRadius: "24px", padding: "40px", textAlign: "center" }}>
            <h2 style={{ fontSize: "28px", fontWeight: 700, marginBottom: "8px" }}>{t.step1}</h2>
            <p style={{ fontSize: "16px", color: "#94A3B8", marginBottom: "28px" }}>{t.placePassport}</p>

            <input
              type="file"
              accept="image/*"
              ref={docInputRef}
              onChange={handleDocChange}
              style={{ display: "none" }}
            />

            <div
              style={{
                height: "280px",
                border: "3px dashed #3B82F6",
                borderRadius: "20px",
                backgroundColor: "rgba(59, 130, 246, 0.05)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "24px",
                overflow: "hidden",
                position: "relative",
              }}
            >
              {docPreview ? (
                <div style={{ width: "100%", height: "100%", position: "relative" }}>
                  <img src={docPreview} alt="Passport Scan" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                  <div style={{ position: "absolute", top: "12px", right: "12px", backgroundColor: "#10B981", color: "#FFF", fontSize: "12px", fontWeight: 700, padding: "4px 10px", borderRadius: "14px" }}>
                    ✓ PASSPORT READY
                  </div>
                </div>
              ) : (
                <>
                  <div style={{ fontSize: "64px", marginBottom: "12px" }}>📑</div>
                  <span style={{ fontSize: "18px", fontWeight: 700, color: "#60A5FA" }}>
                    Scan Passport or Upload Photo
                  </span>
                  <span style={{ fontSize: "13px", color: "#64748B", marginTop: "6px" }}>
                    ICAO 9303 Passports & National ID Cards
                  </span>
                </>
              )}
            </div>

            {/* Passport Acquisition Options */}
            <div className="mb-7 flex flex-wrap justify-center gap-3">
              <Button size="lg" onClick={() => setDocCameraOpen(true)}>
                📸 Live Camera Scanner
              </Button>
              <Button size="lg" variant="secondary" onClick={() => docInputRef.current?.click()}>
                📁 Choose Image File
              </Button>
            </div>

            <div className="flex justify-center gap-3">
              <Button size="lg" variant="ghost" onClick={() => setStep("welcome")}>
                Cancel
              </Button>
              <Button size="lg" disabled={!docFile} onClick={() => setStep("face_capture")}>
                {t.continueBtn}
              </Button>
            </div>
            {!docFile && (
              <p className="mt-3 text-xs text-slate-500">
                Scan or upload your passport to continue.
              </p>
            )}
          </div>
        )}

        {/* Step 3: Face Capture */}
        {step === "face_capture" && (
          <div style={{ width: "100%", maxWidth: "720px", backgroundColor: "#0F172A", border: "2px solid #1E293B", borderRadius: "24px", padding: "40px", textAlign: "center" }}>
            <h2 style={{ fontSize: "28px", fontWeight: 700, marginBottom: "8px" }}>{t.step2}</h2>
            <p style={{ fontSize: "16px", color: "#94A3B8", marginBottom: "24px" }}>{t.lookCamera}</p>

            <input
              type="file"
              accept="image/*"
              capture="user"
              ref={faceInputRef}
              onChange={handleFaceChange}
              style={{ display: "none" }}
            />

            {/* Video Viewport / Photo Snapshot Preview */}
            <div
              style={{
                height: "320px",
                border: "3px solid #10B981",
                borderRadius: "20px",
                backgroundColor: "#020617",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "24px",
                overflow: "hidden",
                position: "relative",
              }}
            >
              {facePreview ? (
                /* Snapped Photo Preview */
                <div style={{ width: "100%", height: "100%", position: "relative" }}>
                  <img src={facePreview} alt="Live Face" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                  <div style={{ position: "absolute", top: "12px", right: "12px", backgroundColor: "#10B981", color: "#FFF", fontSize: "12px", fontWeight: 700, padding: "4px 12px", borderRadius: "14px" }}>
                    ✓ FACE CAPTURED
                  </div>
                </div>
              ) : cameraActive ? (
                /* Real-time WebRTC Live Stream */
                <>
                  <video
                    ref={kioskVideoRef}
                    autoPlay
                    playsInline
                    muted
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      transform: "scaleX(-1)",
                    }}
                  />
                  {/* Biometric Oval Reticle Overlay */}
                  <div
                    style={{
                      position: "absolute",
                      width: "200px",
                      height: "260px",
                      border: "2px dashed #34D399",
                      borderRadius: "50%",
                      boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.45), 0 0 25px rgba(52, 211, 153, 0.4)",
                      pointerEvents: "none",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "14px 0",
                    }}
                  >
                    <span style={{ fontSize: "11px", color: "#34D399", fontWeight: 700, backgroundColor: "rgba(15,23,42,0.8)", padding: "2px 8px", borderRadius: "8px" }}>
                      ALIGN FACE HERE
                    </span>
                    <span style={{ fontSize: "11px", color: "#34D399", fontWeight: 700, backgroundColor: "rgba(15,23,42,0.8)", padding: "2px 8px", borderRadius: "8px" }}>
                      LOOK FORWARD
                    </span>
                  </div>

                  {/* Live Status Pill */}
                  <div style={{ position: "absolute", top: "12px", left: "12px", display: "flex", alignItems: "center", gap: "6px", backgroundColor: "rgba(15, 23, 42, 0.8)", padding: "4px 10px", borderRadius: "20px", border: "1px solid rgba(255,255,255,0.1)" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#10B981", boxShadow: "0 0 8px #10B981" }} />
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "#E2E8F0" }}>LIVE CAMERA</span>
                  </div>
                </>
              ) : (
                /* Fallback if camera not yet active or blocked */
                <div style={{ padding: "20px" }}>
                  <div style={{ fontSize: "56px", marginBottom: "12px" }}>📸</div>
                  <span style={{ fontSize: "16px", fontWeight: 600, color: "#FCA5A5" }}>
                    {kioskCameraError || "Camera starting..."}
                  </span>
                  <div className="mt-4">
                    <Button variant="secondary" onClick={() => faceInputRef.current?.click()}>
                      📁 Upload Face Photo Instead
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Camera Actions Bar */}
            <div className="mb-7 flex flex-wrap items-center justify-center gap-3">
              {!facePreview && cameraActive && (
                <Button size="kiosk" variant="success" onClick={handleSnapKioskPhoto}>
                  📸 Capture Photo
                </Button>
              )}

              {facePreview && (
                <Button variant="secondary" size="lg" onClick={handleRetakeKioskPhoto}>
                  ↺ Retake Photo
                </Button>
              )}

              <Button variant="ghost" size="lg" onClick={() => faceInputRef.current?.click()}>
                📁 Choose File
              </Button>
            </div>

            <div className="flex justify-center gap-3">
              <Button size="lg" variant="ghost" onClick={() => setStep("scan_passport")}>
                Back
              </Button>
              <Button
                size="lg"
                variant="success"
                disabled={!docFile}
                onClick={handleStartProcessing}
              >
                {t.submitScanBtn}
              </Button>
            </div>
            {!faceFile && (
              <p className="mt-3 text-xs text-slate-500">
                A live photo is optional, but without it the biometric face match is skipped.
              </p>
            )}
          </div>
        )}

        {/* Step 4: Automated AI Processing */}
        {step === "processing" && (
          <div style={{ textAlign: "center", maxWidth: "600px" }}>
            <div
              className="spinner"
              style={{
                width: "80px",
                height: "80px",
                border: "6px solid rgba(255,255,255,0.1)",
                borderTopColor: "#3B82F6",
                borderRadius: "50%",
                margin: "0 auto 32px",
                animation: "spin 1s linear infinite",
              }}
            ></div>
            <h2 style={{ fontSize: "30px", fontWeight: 800, marginBottom: "16px" }}>
              {t.processingTitle}
            </h2>
            <p style={{ fontSize: "20px", color: "#60A5FA", fontWeight: 600 }}>
              {processingStage}
            </p>
          </div>
        )}

        {/* Step 5: Verification Result - Real Risk Score Based Decision */}
        {step === "result" && (
          <div style={{
            width: "100%",
            maxWidth: "750px",
            backgroundColor: getResultDisplay().bgColor,
            border: `3px solid ${getResultDisplay().borderColor}`,
            borderRadius: "28px",
            padding: "48px",
            textAlign: "center",
            boxShadow: `0 0 50px ${getResultDisplay().color}33`,
          }}>
            <div style={{ fontSize: "96px", marginBottom: "24px" }}>
              {getResultDisplay().emoji}
            </div>

            <h2 style={{
              fontSize: "36px",
              fontWeight: 900,
              color: getResultDisplay().color,
              marginBottom: "16px",
              letterSpacing: "-1px",
            }}>
              {getResultDisplay().title}
            </h2>

            <p style={{ fontSize: "18px", color: "#E2E8F0", marginBottom: "28px", lineHeight: "1.6" }}>
              {getResultDisplay().description}
            </p>

            {/* Show Evidence Breakdown if Available */}
            {scanResult?.risk_score?.explanations && scanResult.risk_score.explanations.length > 0 && (
              <div style={{
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                padding: "16px 20px",
                borderRadius: "12px",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                marginBottom: "28px",
                textAlign: "left",
                maxHeight: "200px",
                overflowY: "auto"
              }}>
                <div style={{ fontSize: "12px", fontWeight: 700, color: "#94A3B8", marginBottom: "8px", textTransform: "uppercase" }}>
                  Evidence Breakdown:
                </div>
                {scanResult.risk_score.explanations.map((exp: any, idx: number) => (
                  <div key={idx} style={{
                    fontSize: "13px",
                    color: exp.severity === "critical" ? "#FCA5A5" : exp.severity === "high" ? "#FCD34D" : "#A1E8D5",
                    marginBottom: "6px",
                    paddingLeft: "8px",
                    borderLeft: `2px solid ${exp.severity === "critical" ? "#DC2626" : exp.severity === "high" ? "#D97706" : "#059669"}`,
                  }}>
                    {exp.flag}
                  </div>
                ))}
              </div>
            )}

            <Button
              size="kiosk"
              variant={isApproved ? "success" : "secondary"}
              onClick={resetKiosk}
            >
              {t.resetBtn}
            </Button>
          </div>
        )}
      </main>

      {/* Document Scanner Camera Modal */}
      <CameraCaptureModal
        isOpen={docCameraOpen}
        onClose={() => setDocCameraOpen(false)}
        onCapture={handleDocCameraCapture}
        mode="document"
        title="Kiosk Document Scanner"
      />

      {/* Kiosk Footer */}
      <footer style={{ padding: "16px 40px", backgroundColor: "#0F172A", borderTop: "1px solid #1E293B", textAlign: "center", color: "#64748B", fontSize: "13px" }}>
        BORDER GUARD — AI Document & Biometric Screening System • Automated Self-Service Module
      </footer>
    </div>
  );
}
