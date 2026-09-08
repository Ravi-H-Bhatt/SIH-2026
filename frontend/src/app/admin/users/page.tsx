"use client";

import React, { useEffect, useState } from "react";
import { usersApi } from "@/lib/api";
import { User } from "@/types";

export default function UserManagementPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  // Form fields
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("officer");
  const [badgeNumber, setBadgeNumber] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadUsers = async () => {
    try {
      const data = await usersApi.getUsers();
      setUsers(data);
    } catch (err) {
      console.error("Failed to load users", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await usersApi.createUser({
        email,
        full_name: fullName,
        password,
        role,
        badge_number: badgeNumber || undefined,
      });
      setShowModal(false);
      setEmail("");
      setFullName("");
      setPassword("");
      setBadgeNumber("");
      loadUsers();
    } catch (err: any) {
      setError(err.message || "Failed to create user.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 6px" }}>
            Border Officer & User Management
          </h1>
          <p style={{ fontSize: "14px", color: "#94A3B8", margin: 0 }}>
            Manage access privileges, role-based controls, and officer credentials
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          style={{
            padding: "12px 20px",
            borderRadius: "8px",
            background: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
            color: "#FFF",
            fontWeight: 600,
            fontSize: "14px",
            border: "none",
            cursor: "pointer",
            boxShadow: "0 4px 14px rgba(59, 130, 246, 0.4)",
          }}
        >
          ➕ Register New Personnel
        </button>
      </div>

      {/* Users Table */}
      <div style={{ backgroundColor: "rgba(15, 23, 42, 0.6)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
          <thead>
            <tr style={{ backgroundColor: "rgba(30, 41, 59, 0.4)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", color: "#64748B", fontSize: "12px", textTransform: "uppercase" }}>
              <th style={{ padding: "14px 24px" }}>Full Name</th>
              <th style={{ padding: "14px 24px" }}>Email</th>
              <th style={{ padding: "14px 24px" }}>Role</th>
              <th style={{ padding: "14px 24px" }}>Badge #</th>
              <th style={{ padding: "14px 24px" }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} style={{ padding: "32px", textAlign: "center", color: "#94A3B8" }}>
                  Loading users...
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.05)" }}>
                  <td style={{ padding: "16px 24px", color: "#F8FAFC", fontWeight: 600 }}>
                    {u.full_name}
                  </td>
                  <td style={{ padding: "16px 24px", color: "#94A3B8" }}>
                    {u.email}
                  </td>
                  <td style={{ padding: "16px 24px" }}>
                    <span
                      style={{
                        padding: "4px 10px",
                        borderRadius: "12px",
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "uppercase",
                        backgroundColor: u.role === "admin" ? "rgba(239, 68, 68, 0.15)" : u.role === "supervisor" ? "rgba(245, 158, 11, 0.15)" : "rgba(59, 130, 246, 0.15)",
                        color: u.role === "admin" ? "#FCA5A5" : u.role === "supervisor" ? "#FBBF24" : "#93C5FD",
                      }}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: "16px 24px", color: "#CBD5E1", fontFamily: "monospace" }}>
                    {u.badge_number || "—"}
                  </td>
                  <td style={{ padding: "16px 24px", color: u.is_active ? "#34D399" : "#EF4444", fontWeight: 500 }}>
                    {u.is_active ? "ACTIVE" : "INACTIVE"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal dialog for creating new user */}
      {showModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0, 0, 0, 0.7)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ width: "100%", maxWidth: "480px", backgroundColor: "#0F172A", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "16px", padding: "32px" }}>
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#F8FAFC", margin: "0 0 20px" }}>
              Register New Personnel
            </h2>

            {error && (
              <div style={{ backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "#FCA5A5", padding: "10px", borderRadius: "6px", fontSize: "13px", marginBottom: "16px" }}>
                ⚠️ {error}
              </div>
            )}

            <form onSubmit={handleCreateUser}>
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "#CBD5E1", marginBottom: "6px" }}>Full Name</label>
                <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} style={{ width: "100%", padding: "10px", backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", color: "#FFF" }} />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "#CBD5E1", marginBottom: "6px" }}>Official Email</label>
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%", padding: "10px", backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", color: "#FFF" }} />
              </div>

              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "#CBD5E1", marginBottom: "6px" }}>Password</label>
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", padding: "10px", backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", color: "#FFF" }} />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#CBD5E1", marginBottom: "6px" }}>System Role</label>
                  <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: "100%", padding: "10px", backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", color: "#FFF" }}>
                    <option value="officer">Officer</option>
                    <option value="supervisor">Supervisor</option>
                    <option value="investigator">Investigator</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12px", color: "#CBD5E1", marginBottom: "6px" }}>Badge #</label>
                  <input type="text" value={badgeNumber} onChange={(e) => setBadgeNumber(e.target.value)} placeholder="BG-9988" style={{ width: "100%", padding: "10px", backgroundColor: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px", color: "#FFF" }} />
                </div>
              </div>

              <div style={{ display: "flex", gap: "12px" }}>
                <button type="button" onClick={() => setShowModal(false)} style={{ flex: 1, padding: "10px", backgroundColor: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "#94A3B8", borderRadius: "6px", cursor: "pointer" }}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} style={{ flex: 1, padding: "10px", backgroundColor: "#3B82F6", color: "#FFF", border: "none", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}>
                  {isSubmitting ? "Registering..." : "Create Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
