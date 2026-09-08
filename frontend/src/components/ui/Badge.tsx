"use client";

import React from "react";

interface BadgeProps {
  variant?: "low" | "medium" | "high" | "critical" | "approved" | "flagged" | "detained" | "pending";
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ variant = "low", children }) => {
  const getBadgeStyle = () => {
    switch (variant) {
      case "critical":
      case "detained":
        return { bg: "rgba(239, 68, 68, 0.2)", text: "#FCA5A5", border: "1px solid rgba(239, 68, 68, 0.4)" };
      case "high":
      case "flagged":
        return { bg: "rgba(245, 158, 11, 0.2)", text: "#FDE047", border: "1px solid rgba(245, 158, 11, 0.4)" };
      case "medium":
        return { bg: "rgba(234, 179, 8, 0.15)", text: "#FEF08A", border: "1px solid rgba(234, 179, 8, 0.3)" };
      case "approved":
        return { bg: "rgba(16, 185, 129, 0.2)", text: "#6EE7B7", border: "1px solid rgba(16, 185, 129, 0.4)" };
      case "pending":
        return { bg: "rgba(59, 130, 246, 0.15)", text: "#93C5FD", border: "1px solid rgba(59, 130, 246, 0.3)" };
      default:
        return { bg: "rgba(16, 185, 129, 0.15)", text: "#6EE7B7", border: "1px solid rgba(16, 185, 129, 0.3)" };
    }
  };

  const style = getBadgeStyle();

  return (
    <span
      style={{
        padding: "4px 10px",
        borderRadius: "12px",
        fontSize: "12px",
        fontWeight: 600,
        backgroundColor: style.bg,
        color: style.text,
        border: style.border,
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
      }}
    >
      {children}
    </span>
  );
};
