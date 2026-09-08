"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { User, LoginResponse } from "@/types";
import { authApi } from "@/lib/api";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: any) => Promise<LoginResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ── Dev bypass: inject a demo admin user so you go straight to the dashboard ─
const BYPASS_AUTH = process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";

const DEMO_USER: User = {
  id: "demo-admin-001",
  email: "admin@borderguard.sih",
  full_name: "Demo Admin",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString(),
};

const DEMO_TOKEN = "demo-bypass-token-sih26188";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(BYPASS_AUTH ? DEMO_USER : null);
  const [token, setToken] = useState<string | null>(BYPASS_AUTH ? DEMO_TOKEN : null);
  const [isLoading, setIsLoading] = useState(!BYPASS_AUTH);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // If bypass is enabled, we already have a demo user — skip localStorage check
    if (BYPASS_AUTH) {
      setIsLoading(false);
      return;
    }

    const storedToken = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (credentials: any): Promise<LoginResponse> => {
    // In bypass mode, immediately resolve with the demo user
    if (BYPASS_AUTH) {
      setToken(DEMO_TOKEN);
      setUser(DEMO_USER);
      return {
        access_token: DEMO_TOKEN,
        token_type: "bearer",
        user: DEMO_USER,
      };
    }

    const response = await authApi.login(credentials);
    const loggedInUser = response.user || {
      id: response.user_id || "1",
      email: response.email || credentials.email,
      full_name: response.full_name || "User",
      role: response.role || "officer",
      is_active: true,
      created_at: new Date().toISOString(),
    };
    setToken(response.access_token);
    setUser(loggedInUser);
    localStorage.setItem("token", response.access_token);
    localStorage.setItem("user", JSON.stringify(loggedInUser));
    return {
      access_token: response.access_token,
      token_type: response.token_type,
      user: loggedInUser,
    };
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    if (!BYPASS_AUTH) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      router.push("/login");
    } else {
      // In bypass mode, just re-inject the demo user silently
      setToken(DEMO_TOKEN);
      setUser(DEMO_USER);
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
