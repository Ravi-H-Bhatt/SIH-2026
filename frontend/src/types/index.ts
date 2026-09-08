/* ===================================================
   TypeScript types matching the backend Pydantic schemas.
   This is the single source of truth for frontend types.
   =================================================== */

// ─── Auth ─────────────────────────────────────
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id?: string;
  email?: string;
  full_name?: string;
  role?: UserRole;
  user?: User;
}

// ─── Users ────────────────────────────────────
export type UserRole = "admin" | "officer" | "supervisor" | "investigator";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  badge_number?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  full_name: string;
  password: string;
  role: UserRole | string;
  badge_number?: string;
}

export interface UserListResponse {
  users: User[];
  total: number;
}

// ─── Scans ────────────────────────────────────
export type DocumentType = "passport" | "visa" | "id_card" | "driving_license" | "permit" | string;
export type ScanStatus = "pending" | "processing" | "completed" | "failed";
export type Decision = "approved" | "flagged" | "detained" | "pending" | string;
export type RiskLevel = "low" | "medium" | "high" | "critical" | string;

export interface ExtractedData {
  nationality?: string;
  expiry_date?: string;
  mrz_lines?: string[];
  fields?: Record<string, unknown> | null;
  mrz_data?: Record<string, unknown> | null;
  mrz_valid?: boolean | null;
}

export interface ForgeryResult {
  anomaly_score?: number | null;
  detected_issues?: Array<{
    type: string;
    confidence: number;
    detail: string;
  }> | null;
}

export interface FaceResult {
  crop_path?: string | null;
  similarity_score?: number | null;
  is_live?: boolean | null;
  match_score?: number | null;
  liveness_passed?: boolean | null;
  watchlist_hits?: Array<{
    name: string;
    confidence: number;
    source: string;
  }> | null;
}

export interface ContradictionItem {
  category: string;
  check_name: string;
  signal_a: string;
  signal_b: string;
  status: "PASS" | "CONTRADICTION" | "ALERT" | string;
  severity: "LOW" | "HIGH" | "CRITICAL" | string;
  finding: string;
}

export interface IdentityGraphNode {
  id: string;
  label: string;
  type: string;
  is_current?: boolean;
}

export interface IdentityGraphEdge {
  source: string;
  target: string;
  relation: string;
  similarity?: number;
}

export interface IdentityGraphAnomaly {
  type: string;
  severity: string;
  confidence: number;
  description: string;
  past_identity?: Record<string, unknown>;
}

export interface IdentityGraphSummary {
  nodes?: IdentityGraphNode[];
  edges?: IdentityGraphEdge[];
  anomalies?: IdentityGraphAnomaly[];
  continuity_links?: Array<{
    scan_id: string;
    document_number: string;
    holder_name: string;
    date_of_birth?: string;
    biometric_similarity: number;
    encounter_date?: string;
  }>;
  has_graph_anomalies?: boolean;
}

export interface FraudPatternMatch {
  pattern_id: string;
  name: string;
  confidence: number;
  severity: string;
  description: string;
  countermeasure: string;
}

export interface RiskScore {
  score?: number | null;
  level?: RiskLevel | null;
  risk_level?: RiskLevel | null;
  flags?: string[] | null;
  explanations?: Array<{
    flag: string;
    severity: string;
  }> | null;
  decision?: string | null;
  contradiction_matrix?: ContradictionItem[] | null;
  identity_graph_summary?: IdentityGraphSummary | null;
  fraud_patterns_matched?: FraudPatternMatch[] | null;
  canonical_hash?: string | null;
}

export interface ScanRecord {
  id: string;
  document_type: DocumentType;
  issuing_country?: string;
  document_number?: string;
  holder_name?: string;
  status: ScanStatus;
  checkpoint_id?: string | null;
  officer_id?: string | null;
  officer_name?: string | null;
  document_image_path?: string | null;
  face_image_path?: string | null;
  notes?: string | null;
  decision: Decision;
  final_decision?: Decision | null;
  chip_pki_status?: string | null;
  canonical_hash?: string | null;
  created_at: string;
  updated_at?: string | null;
  extracted_data?: ExtractedData | null;
  forgery_results?: ForgeryResult | null;
  forgery_result?: ForgeryResult | null;
  face_results?: FaceResult | null;
  face_result?: FaceResult | null;
  risk_score?: RiskScore | null;
}

export type Scan = ScanRecord;

export interface ScanListResponse {
  scans: ScanRecord[];
  total: number;
  page?: number;
  page_size?: number;
}

// ─── Dashboard ────────────────────────────────
export interface DashboardStats {
  total_scans?: number;
  total_scans_today?: number;
  total_scans_all?: number;
  approved_today?: number;
  flagged_today?: number;
  detained_today?: number;
  pending_review?: number;
  decisions_breakdown?: {
    approved: number;
    flagged: number;
    detained: number;
    pending: number;
  };
  risk_breakdown?: {
    low: number;
    medium: number;
    high: number;
    critical: number;
  };
  risk_distribution?: Record<string, number>;
  avg_processing_time?: number;
}

// ─── Audit ────────────────────────────────────
export interface AuditLog {
  id: string;
  scan_id?: string | null;
  user_id?: string | null;
  actor?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  ip_address?: string | null;
  timestamp?: string;
  created_at: string;
  details?: Record<string, unknown> | null;
  hash?: string | null;
}

export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
  page?: number;
  page_size?: number;
}

// ─── Operations map (GET /api/v1/dashboard/map) ───────────────────────────

export interface MapCheckpoint {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  total_scans: number;
  flagged: number;
}

export interface MapPoint {
  scan_id: string;
  latitude: number;
  longitude: number;
  holder_name: string;
  document_number: string;
  document_type: string;
  issuing_country: string | null;
  country_name: string | null;
  risk_level: string;
  risk_score: number;
  decision: string;
  checkpoint_id: string;
  is_criminal: boolean;
  is_wanted: boolean;
  created_at: string | null;
}

export interface OperationsMapData {
  checkpoints: MapCheckpoint[];
  points: MapPoint[];
  total_points: number;
  /** Backend disclaimer: origins are country centroids, not address geocodes. */
  geocode_note: string;
}
