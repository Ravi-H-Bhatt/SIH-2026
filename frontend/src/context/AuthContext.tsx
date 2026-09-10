"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { User, LoginResponse } from "@/types";
import { api, authApi, TOKEN_STORAGE_KEY, USER_STORAGE_KEY } from "@/lib/api";
import { getSupabaseClient } from "@/lib/supabaseClient";
import { useRouter } from "next/navigation";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<LoginResponse>;
  loginWithGoogle: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * The previous implementation had a NEXT_PUBLIC_BYPASS_AUTH mode that injected a
 * synthetic admin user plus a hardcoded "demo-bypass-token-sih26188" token and
 * skipped the backend entirely. It has been removed: the token was a constant
 * committed to the repo, and the backend had a matching branch that accepted it
 * as a full admin. Every session now originates from a real backend JWT.
 */

function toUser(res: any, fallbackEmail?: string): User {
  return (
    res.user || {
      id: res.user_id || "unknown",
      email: res.email || fallbackEmail || "",
      full_name: res.full_name || "User",
      role: res.role || "officer",
      is_active: true,
      created_at: new Date().toISOString(),
    }
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const persist = useCallback((accessToken: string, nextUser: User) => {
    setToken(accessToken);
    setUser(nextUser);
    api.setToken(accessToken);
    if (typeof window !== "undefined") {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(nextUser));
    }
  }, []);

  useEffect(() => {
    // Restore from the same key the API client uses. These used to differ
    // ("token" here vs "access_token" in the client), so a refreshed page showed
    // a logged-in user while every request went out unauthenticated.
    const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
    const storedUser = localStorage.getItem(USER_STORAGE_KEY);

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(toUser(JSON.parse(storedUser)));
        api.setToken(storedToken);
      } catch {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        localStorage.removeItem(USER_STORAGE_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (credentials: { email: string; password: string }): Promise<LoginResponse> => {
    const response = await authApi.login(credentials);
    const loggedInUser = toUser(response, credentials.email);
    persist(response.access_token, loggedInUser);
    return {
      access_token: response.access_token,
      token_type: response.token_type,
      user: loggedInUser,
    };
  };

  /**
   * Starts the Google OAuth redirect through Supabase. The exchange for an
   * application JWT happens on return, in the /auth/callback route.
   */
  const loginWithGoogle = async (): Promise<void> => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error(
        "Google sign-in is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
      );
    }
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { prompt: "select_account" },
      },
    });
    if (error) throw new Error(error.message);
  };

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    api.clearToken();
    // Also drop the Supabase session so "sign out" does not silently re-authenticate.
    getSupabaseClient()?.auth.signOut().catch(() => undefined);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, loginWithGoogle, logout }}>
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
