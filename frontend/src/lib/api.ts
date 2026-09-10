/**
 * API Client — centralized HTTP client for the backend API.
 * Handles JWT token management and request/response formatting.
 */

import type { TokenResponse, LoginRequest } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Single source of truth for where the application JWT lives. AuthContext used
// to write localStorage["token"] while this client read localStorage["access_token"],
// so a page reload restored the user but sent no Authorization header.
export const TOKEN_STORAGE_KEY = "access_token";
export const USER_STORAGE_KEY = "user";

// The demo bypass that used to live here is gone. It short-circuited getToken()
// to return a hardcoded "demo-bypass-token-sih26188" string, and the backend had
// a matching branch that accepted it as a synthetic admin — a permanent,
// publicly-known admin credential.

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem(TOKEN_STORAGE_KEY);
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      localStorage.removeItem(USER_STORAGE_KEY);
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== "undefined") {
      this.token = localStorage.getItem(TOKEN_STORAGE_KEY);
    }
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    // Add auth header if token exists
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    // Add content-type for JSON (unless it's FormData)
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    // A bare `fetch` rejection surfaces as the opaque "Failed to fetch", which
    // gives an officer no idea whether the server is down, still starting, or
    // rejecting the origin. Translate it into something actionable.
    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch (networkError) {
      throw new Error(
        `Cannot reach the screening API at ${API_BASE}. ` +
          `The backend may be starting up (it takes ~15s), stopped, or blocking ` +
          `this origin via CORS. Original error: ` +
          `${networkError instanceof Error ? networkError.message : String(networkError)}`
      );
    }

    if (response.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // ─── Auth ──────────────────────────────────
  async login(data: LoginRequest): Promise<TokenResponse> {
    const res = await this.request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
    this.setToken(res.access_token);
    if (typeof window !== "undefined") {
      localStorage.setItem("user", JSON.stringify(res));
    }
    return res;
  }

  /**
   * Exchanges a verified Supabase/Google session for an application JWT.
   * The Supabase token is only ever sent to our own backend, which validates it
   * against Supabase before issuing the application token.
   */
  async loginWithGoogle(supabaseAccessToken: string): Promise<TokenResponse> {
    const res = await this.request<TokenResponse>("/api/v1/auth/google", {
      method: "POST",
      body: JSON.stringify({ access_token: supabaseAccessToken }),
    });
    this.setToken(res.access_token);
    if (typeof window !== "undefined") {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(res));
    }
    return res;
  }

  /** Which sign-in methods the backend actually supports. */
  async getAuthProviders() {
    return this.request<{ password: boolean; google: boolean }>(
      "/api/v1/auth/providers"
    );
  }

  async refreshToken(): Promise<TokenResponse> {
    return this.request<TokenResponse>("/api/v1/auth/refresh", {
      method: "POST",
    });
  }

  // ─── Dashboard ──────────────────────────────
  async getDashboardStats() {
    return this.request<import("@/types").DashboardStats>("/api/v1/dashboard/stats");
  }

  async getOperationsMap(limit = 200) {
    return this.request<import("@/types").OperationsMapData>(
      `/api/v1/dashboard/map?limit=${limit}`
    );
  }

  // ─── Scans ──────────────────────────────────
  /**
   * Travellers gallery — scans with signed document/face image URLs attached.
   *
   * `include_images` is opt-in because it costs one Supabase round-trip per
   * image, so page_size is kept small here.
   */
  async getTravellers(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    risk_level?: string;
    decision?: string;
    document_type?: string;
  }) {
    const sp = new URLSearchParams({ include_images: "true" });
    sp.set("page", String(params?.page ?? 1));
    sp.set("page_size", String(params?.page_size ?? 12));
    if (params?.search) sp.set("search", params.search);
    if (params?.risk_level) sp.set("risk_level", params.risk_level);
    if (params?.decision) sp.set("decision", params.decision);
    if (params?.document_type) sp.set("document_type", params.document_type);
    return this.request<import("@/types").ScanListResponse>(`/api/v1/scans?${sp}`);
  }

  async getScans(params?: {
    page?: number;
    page_size?: number;
    status?: string;
    document_type?: string;
    decision?: string;
  }) {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString() ? `?${searchParams}` : "";
    return this.request<import("@/types").ScanListResponse>(`/api/v1/scans${query}`);
  }

  async getScan(id: string) {
    return this.request<import("@/types").Scan>(`/api/v1/scans/${id}`);
  }

  async createScan(formData: FormData) {
    return this.request<import("@/types").Scan>("/api/v1/scans", {
      method: "POST",
      body: formData,
    });
  }

  async makeScanDecision(scanId: string, decision: string, notes?: string) {
    return this.request<import("@/types").Scan>(`/api/v1/scans/${scanId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    });
  }

  async verifyAuditIntegrity(scanId: string) {
    return this.request<{
      verified: boolean;
      canonical_hash: string;
      algorithm: string;
      evidence_version: string;
      status: string;
      timestamp: string;
      integrity_message: string;
    }>(`/api/v1/scans/${scanId}/verify-audit`, {
      method: "POST",
    });
  }

  // ─── Supervisor ──────────────────────────────
  async getSupervisorDashboard() {
    return this.request<{
      total_scans_today: number;
      flagged_queue_count: number;
      active_checkpoints_count: number;
      officers_on_duty_count: number;
      checkpoints: Array<{
        id: string;
        name: string;
        status: string;
        queue_length: number;
        throughput_per_hour: number;
        avg_processing_sec: number;
      }>;
      officers: Array<{
        id: string;
        name: string;
        role: string;
        email: string;
        scans_processed: number;
        status: string;
      }>;
    }>("/api/v1/supervisor/dashboard");
  }

  async getFlaggedQueue(page = 1, pageSize = 20) {
    return this.request<{
      flagged_cases: Array<{
        id: string;
        document_type: string;
        status: string;
        final_decision: string | null;
        checkpoint_id: string;
        officer_name: string;
        holder_name: string;
        document_number: string;
        issuing_country: string;
        overall_risk_score: number;
        risk_level: string;
        explanations: Array<{ flag: string; severity: string }>;
        created_at: string;
      }>;
      total: number;
      page: number;
      page_size: number;
    }>(`/api/v1/supervisor/flagged-queue?page=${page}&page_size=${pageSize}`);
  }

  async overrideDecision(scanId: string, decision: string, notes?: string) {
    return this.request<{
      success: boolean;
      scan_id: string;
      final_decision: string;
      notes: string;
    }>(`/api/v1/supervisor/override/${scanId}`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    });
  }

  // ─── Users ──────────────────────────────────
  async getUsers(skip = 0, limit = 50) {
    return this.request<import("@/types").UserListResponse>(
      `/api/v1/users?skip=${skip}&limit=${limit}`
    );
  }

  async createUser(data: import("@/types").UserCreate) {
    return this.request<import("@/types").User>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // ─── Audit ──────────────────────────────────
  async getAuditLogs(params?: {
    page?: number;
    page_size?: number;
    action?: string;
    actor?: string;
    scan_id?: string;
  }) {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString() ? `?${searchParams}` : "";
    return this.request<import("@/types").AuditLogListResponse>(`/api/v1/audit/logs${query}`);
  }

  // ─── Biometrics ──────────────────────────────
  //
  // Every similarity these return is a raw SFace cosine in [-1, 1]. Do not
  // rescale it in the UI — display the number the model produced.

  /** 1:1 — compare two uploaded images directly. */
  async compareFaces(imageA: File, imageB: File) {
    const form = new FormData();
    form.append("image_a", imageA);
    form.append("image_b", imageB);
    return this.request<import("@/types").FaceCompareResponse>("/api/v1/face/compare", {
      method: "POST",
      body: form,
    });
  }

  /** 1:N — identify a probe face against every stored encounter. */
  async searchFaces(image: File, topK = 10) {
    const form = new FormData();
    form.append("image", image);
    form.append("top_k", String(topK));
    return this.request<import("@/types").FaceSearchResponse>("/api/v1/face/search", {
      method: "POST",
      body: form,
    });
  }

  /** Gallery diagnostics — how many stored embeddings are actually comparable. */
  async faceGalleryHealth() {
    return this.request<import("@/types").FaceGalleryHealth>("/api/v1/face/gallery");
  }

  // ─── Health ──────────────────────────────────
  async healthCheck() {
    return this.request<{ status: string; database: string }>("/api/v1/health");
  }
}

export const api = new ApiClient();
export const apiClient = api;

export const authApi = {
  login: (data: LoginRequest) => api.login(data),
  refreshToken: () => api.refreshToken(),
};

export const dashboardApi = {
  getStats: () => api.getDashboardStats(),
  getOperationsMap: (limit = 200) => api.getOperationsMap(limit),
};

export const scansApi = {
  getScans: (params?: { page?: number; page_size?: number; limit?: number; status?: string; document_type?: string; decision?: string }) => api.getScans(params),
  getTravellers: (params?: { page?: number; page_size?: number; search?: string; risk_level?: string; decision?: string; document_type?: string }) => api.getTravellers(params),
  getScan: (id: string) => api.getScan(id),
  uploadScan: (formData: FormData) => api.createScan(formData),
  makeDecision: (scanId: string, decision: string, notes?: string) => api.makeScanDecision(scanId, decision, notes),
  verifyAuditIntegrity: (scanId: string) => api.verifyAuditIntegrity(scanId),
};

export const supervisorApi = {
  getDashboard: () => api.getSupervisorDashboard(),
  getFlaggedQueue: (page = 1, pageSize = 20) => api.getFlaggedQueue(page, pageSize),
  overrideDecision: (scanId: string, decision: string, notes?: string) => api.overrideDecision(scanId, decision, notes),
};

export const usersApi = {
  getUsers: (skip = 0, limit = 50) => api.getUsers(skip, limit).then(res => Array.isArray(res) ? res : res.users || []),
  createUser: (data: import("@/types").UserCreate) => api.createUser(data),
};

export const faceApi = {
  compare: (a: File, b: File) => api.compareFaces(a, b),
  search: (image: File, topK = 10) => api.searchFaces(image, topK),
  galleryHealth: () => api.faceGalleryHealth(),
};

export const auditApi = {
  getLogs: (params?: { page?: number; page_size?: number; limit?: number; action?: string; actor?: string; scan_id?: string }) => api.getAuditLogs(params).then(res => ({ logs: res.logs || [], total: res.total || 0 })),
};

export default api;
