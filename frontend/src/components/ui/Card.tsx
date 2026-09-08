"use client";

import React from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  headerAction?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  headerAction,
  children,
  style,
}) => {
  return (
    <div
      style={{
        backgroundColor: "var(--bg-secondary)",
        borderRadius: "12px",
        border: "1px solid var(--border-color)",
        padding: "24px",
        boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
        ...style,
      }}
    >
      {(title || headerAction) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
          <div>
            {title && <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#F8FAFC", margin: 0 }}>{title}</h3>}
            {subtitle && <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "4px 0 0 0" }}>{subtitle}</p>}
          </div>
          {headerAction}
        </div>
      )}
      {children}
    </div>
  );
};
