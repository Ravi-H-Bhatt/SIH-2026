"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

interface CameraCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File, previewUrl: string) => void;
  mode: "document" | "face";
  title?: string;
}

export default function CameraCaptureModal({
  isOpen,
  onClose,
  onCapture,
  mode,
  title,
}: CameraCaptureModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const autoCaptureLockRef = useRef<boolean>(false);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"user" | "environment">(
    mode === "face" ? "user" : "environment"
  );
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [autoDetectStatus, setAutoDetectStatus] = useState<string>("Detecting...");

  const stopStream = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
  }, [stream]);

  const startCamera = useCallback(async () => {
    setIsInitializing(true);
    setCameraError(null);

    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("WebRTC Camera is not supported in this browser.");
      }

      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: facingMode,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      setStream(mediaStream);

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err: any) {
      console.error("[Camera] Error:", err);
      let message = "Could not access camera.";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        message = "Camera permission denied. Please allow camera access in browser settings.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        message = "No camera device found.";
      }
      setCameraError(message);
    } finally {
      setIsInitializing(false);
    }
  }, [facingMode, stream]);

  // Auto-detect and auto-capture when subject is in frame
  useEffect(() => {
    if (!videoRef.current || capturedImage || !stream || autoCaptureLockRef.current) {
      return;
    }

    const detectionInterval = setInterval(() => {
      const video = videoRef.current;
      if (!video || autoCaptureLockRef.current || !video.videoWidth) return;

      const canvas = canvasRef.current || document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;

      // Analyze image for presence of face/document
      let brightPixels = 0;
      let darkPixels = 0;
      let skinTonePixels = 0;

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const brightness = (r + g + b) / 3;

        if (brightness > 180) brightPixels++;
        if (brightness < 50) darkPixels++;

        // Detect skin tones for face
        if (r > 95 && g > 40 && b > 20 && Math.max(r, g, b) - Math.min(r, g, b) > 15) {
          skinTonePixels++;
        }
      }

      const hasContrast = brightPixels > 100 && darkPixels > 100;
      const faceDetected = skinTonePixels > canvas.width * canvas.height * 0.08;
      const documentDetected = hasContrast && skinTonePixels < canvas.width * canvas.height * 0.05;

      const shouldCapture =
        (mode === "face" && faceDetected) ||
        (mode === "document" && documentDetected);

      if (shouldCapture) {
        setAutoDetectStatus("✓ Detected! Capturing...");
        autoCaptureLockRef.current = true;

        canvas.toBlob(
          (blob) => {
            if (!blob) return;
            const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
            setCapturedBlob(blob);
            setCapturedImage(dataUrl);
            setAutoDetectStatus("Image Captured!");
          },
          "image/jpeg",
          0.95
        );
      } else {
        setAutoDetectStatus(mode === "face" ? "Detecting face..." : "Detecting document...");
      }
    }, 500);

    return () => clearInterval(detectionInterval);
  }, [mode, stream, capturedImage]);

  useEffect(() => {
    if (isOpen) {
      setCapturedImage(null);
      setCapturedBlob(null);
      setCameraError(null);
      autoCaptureLockRef.current = false;
      setAutoDetectStatus("Initializing camera...");
      startCamera();
    } else {
      stopStream();
      autoCaptureLockRef.current = false;
    }

    return () => {
      stopStream();
    };
  }, [isOpen]);

  useEffect(() => {
    if (videoRef.current && stream && !capturedImage) {
      videoRef.current.srcObject = stream;
    }
  }, [stream, capturedImage]);

  const handleCapture = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current || document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    if (facingMode === "user") {
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
        setCapturedBlob(blob);
        setCapturedImage(dataUrl);
      },
      "image/jpeg",
      0.95
    );
  };

  const handleRetake = () => {
    setCapturedImage(null);
    setCapturedBlob(null);
    autoCaptureLockRef.current = false;
    setAutoDetectStatus("Detecting...");
  };

  const handleConfirm = () => {
    if (!capturedBlob || !capturedImage) return;
    const fileName =
      mode === "face"
        ? `live_face_${Date.now()}.jpg`
        : `document_scan_${Date.now()}.jpg`;
    const file = new File([capturedBlob], fileName, { type: "image/jpeg" });
    onCapture(file, capturedImage);
    stopStream();
    autoCaptureLockRef.current = false;
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(3, 7, 18, 0.85)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "760px",
          backgroundColor: "#0F172A",
          border: "1px solid rgba(59, 130, 246, 0.3)",
          borderRadius: "16px",
          overflow: "hidden",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(59, 130, 246, 0.2)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            backgroundColor: "#1E293B",
            borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "20px" }}>{mode === "face" ? "👤" : "📄"}</span>
            <div>
              <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#F8FAFC", margin: 0 }}>
                {title || (mode === "face" ? "Live Biometric Face Capture" : "Document Camera Scanner")}
              </h2>
              <p style={{ fontSize: "12px", color: "#94A3B8", margin: "2px 0 0" }}>
                Auto-detecting and capturing when subject is in frame...
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              stopStream();
              onClose();
            }}
            style={{
              background: "transparent",
              border: "none",
              color: "#94A3B8",
              fontSize: "20px",
              cursor: "pointer",
              padding: "4px 8px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Viewport */}
        <div
          style={{
            position: "relative",
            width: "100%",
            height: "440px",
            backgroundColor: "#020617",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {cameraError ? (
            <div style={{ padding: "32px", textAlign: "center" }}>
              <div style={{ fontSize: "42px", marginBottom: "12px" }}>⚠️</div>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#FCA5A5", marginBottom: "8px" }}>
                Camera Access Unavailable
              </h3>
              <p style={{ fontSize: "13px", color: "#94A3B8" }}>{cameraError}</p>
            </div>
          ) : capturedImage ? (
            <div style={{ width: "100%", height: "100%", position: "relative" }}>
              <img
                src={capturedImage}
                alt="Captured"
                style={{ width: "100%", height: "100%", objectFit: "contain", backgroundColor: "#000" }}
              />
              <div
                style={{
                  position: "absolute",
                  top: "12px",
                  right: "12px",
                  padding: "4px 10px",
                  borderRadius: "20px",
                  backgroundColor: "rgba(16, 185, 129, 0.2)",
                  border: "1px solid #10B981",
                  color: "#34D399",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                ✓ Image Captured
              </div>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transform: facingMode === "user" ? "scaleX(-1)" : "none",
                }}
              />

              {/* Reticle */}
              {mode === "face" ? (
                <div
                  style={{
                    position: "absolute",
                    width: "240px",
                    height: "310px",
                    border: "2px dashed #38BDF8",
                    borderRadius: "50%",
                    boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.55), 0 0 20px rgba(56, 189, 248, 0.4)",
                    pointerEvents: "none",
                  }}
                />
              ) : (
                <div
                  style={{
                    position: "absolute",
                    width: "82%",
                    height: "76%",
                    border: "2px solid #3B82F6",
                    borderRadius: "12px",
                    boxShadow: "0 0 0 9999px rgba(3, 7, 18, 0.55), 0 0 25px rgba(59, 130, 246, 0.35)",
                    pointerEvents: "none",
                  }}
                />
              )}

              {/* Status */}
              <div
                style={{
                  position: "absolute",
                  top: "14px",
                  left: "14px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  backgroundColor: "rgba(15, 23, 42, 0.75)",
                  padding: "6px 12px",
                  borderRadius: "20px",
                  fontSize: "11px",
                  fontWeight: 600,
                  color: "#E2E8F0",
                }}
              >
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    backgroundColor: "#10B981",
                    boxShadow: "0 0 8px #10B981",
                  }}
                />
                {autoDetectStatus}
              </div>
            </>
          )}

          <canvas ref={canvasRef} style={{ display: "none" }} />
        </div>

        {/* Footer Controls */}
        <div
          style={{
            padding: "16px 20px",
            backgroundColor: "#1E293B",
            borderTop: "1px solid rgba(255, 255, 255, 0.1)",
            display: "flex",
            gap: "12px",
            justifyContent: "flex-end",
          }}
        >
          {capturedImage ? (
            <>
              <button
                onClick={handleRetake}
                style={{
                  padding: "10px 20px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  color: "#CBD5E1",
                  fontSize: "14px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                ↺ Retake
              </button>
              <button
                onClick={handleConfirm}
                style={{
                  padding: "10px 24px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                  border: "none",
                  color: "#FFFFFF",
                  fontSize: "14px",
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                }}
              >
                ✓ Use This Photo
              </button>
            </>
          ) : (
            <button
              onClick={handleCapture}
              disabled={Boolean(cameraError) || isInitializing}
              style={{
                padding: "10px 24px",
                borderRadius: "8px",
                background:
                  cameraError || isInitializing
                    ? "rgba(30, 41, 59, 0.5)"
                    : "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
                border: "none",
                color: cameraError || isInitializing ? "#64748B" : "#FFFFFF",
                fontSize: "14px",
                fontWeight: 700,
                cursor: cameraError || isInitializing ? "not-allowed" : "pointer",
                boxShadow: cameraError || isInitializing ? "none" : "0 4px 16px rgba(59, 130, 246, 0.4)",
              }}
            >
              📸 Capture or Auto-Detect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
