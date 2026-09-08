-- ============================================================================
-- SUPABASE COMPLETE DATABASE SCHEMA
-- SIH 26188 - AI Border Document Screening System
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_cron for scheduled tasks
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE user_role AS ENUM (
    'ADMIN',
    'SUPERVISOR', 
    'OFFICER',
    'ANALYST',
    'AUDITOR'
);

CREATE TYPE screening_status AS ENUM (
    'IN_PROGRESS',
    'COMPLETED',
    'ESCALATED',
    'ARCHIVED'
);

CREATE TYPE risk_level AS ENUM (
    'CLEAR',
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);

CREATE TYPE decision_type AS ENUM (
    'CLEAR',
    'SECONDARY_REVIEW',
    'ESCALATE',
    'DETAIN'
);

CREATE TYPE contradiction_type AS ENUM (
    'TEMPORAL',
    'IDENTITY',
    'DOCUMENT',
    'BEHAVIORAL',
    'BIOMETRIC',
    'CROSS_SOURCE'
);

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Users (Officers, Supervisors, Admins)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'OFFICER',
    station_id VARCHAR(50),
    badge_number VARCHAR(50) UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Border Stations
CREATE TABLE stations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location_city VARCHAR(100),
    location_state VARCHAR(100),
    location_country VARCHAR(3) DEFAULT 'IND',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    station_type VARCHAR(50), -- 'AIRPORT', 'SEAPORT', 'LAND_BORDER'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Screenings (Main screening records)
CREATE TABLE screenings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    officer_id UUID REFERENCES users(id),
    station_id UUID REFERENCES stations(id),
    status screening_status DEFAULT 'IN_PROGRESS',
    risk_level risk_level,
    risk_score DECIMAL(5, 4), -- 0.0000 to 1.0000
    confidence DECIMAL(5, 4),
    recommended_action decision_type,
    officer_decision decision_type,
    officer_notes TEXT,
    reasoning TEXT,
    
    -- Traveler info (hashed/encrypted)
    traveler_name_hash VARCHAR(255),
    document_number_hash VARCHAR(255),
    nationality VARCHAR(3),
    
    -- Timestamps
    screening_started_at TIMESTAMPTZ DEFAULT NOW(),
    screening_completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documents (Scanned documents)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_type VARCHAR(50), -- 'PASSPORT', 'ID_CARD', 'VISA'
    document_number VARCHAR(100),
    issuing_country VARCHAR(3),
    issue_date DATE,
    expiry_date DATE,
    
    -- Storage
    document_image_url TEXT, -- Supabase Storage URL
    document_hash VARCHAR(255),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- MRZ Records
CREATE TABLE mrz_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    -- MRZ Data
    mrz_type VARCHAR(10), -- 'TD1', 'TD3'
    mrz_raw_text TEXT,
    is_valid BOOLEAN,
    
    -- Parsed fields
    document_number VARCHAR(100),
    surname VARCHAR(100),
    given_names VARCHAR(100),
    nationality VARCHAR(3),
    date_of_birth DATE,
    sex VARCHAR(1),
    date_of_expiry DATE,
    personal_number VARCHAR(50),
    
    -- Validation
    check_digits_valid BOOLEAN,
    composite_check_valid BOOLEAN,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- OCR Results
CREATE TABLE ocr_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    -- OCR data
    full_text TEXT,
    confidence DECIMAL(5, 4),
    language VARCHAR(10),
    
    -- Extracted fields (JSONB for flexibility)
    extracted_fields JSONB,
    
    -- Bounding boxes
    field_locations JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Forensic Results
CREATE TABLE forensic_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Overall assessment
    tampering_probability DECIMAL(5, 4),
    confidence DECIMAL(5, 4),
    
    -- Individual signals (JSONB)
    ela_score DECIMAL(5, 4),
    metadata_score DECIMAL(5, 4),
    compression_score DECIMAL(5, 4),
    noise_score DECIMAL(5, 4),
    edge_score DECIMAL(5, 4),
    copy_move_score DECIMAL(5, 4),
    
    signals JSONB,
    suspicious_regions JSONB,
    explanation TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Validation Results
CREATE TABLE validation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    is_valid BOOLEAN,
    validation_score DECIMAL(5, 4),
    rules_checked INTEGER,
    rules_passed INTEGER,
    rules_failed INTEGER,
    
    -- Findings (JSONB array)
    findings JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Face Captures
CREATE TABLE face_captures (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    
    -- Storage
    face_image_url TEXT,
    face_hash VARCHAR(255),
    
    -- Quality metrics
    quality_score DECIMAL(5, 4),
    sharpness DECIMAL(5, 4),
    brightness DECIMAL(5, 4),
    contrast DECIMAL(5, 4),
    is_frontal BOOLEAN,
    
    -- Liveness
    liveness_result VARCHAR(20),
    liveness_score DECIMAL(5, 4),
    
    -- Embedding (encrypted/hashed)
    embedding_hash VARCHAR(255),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Face Verification Results
CREATE TABLE face_verification_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id),
    face_capture_id UUID REFERENCES face_captures(id),
    
    similarity DECIMAL(5, 4),
    is_match BOOLEAN,
    confidence DECIMAL(5, 4),
    threshold_used DECIMAL(5, 4),
    
    explanation TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Identity Entities (for graph)
CREATE TABLE identity_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(20), -- 'PERSON', 'DOCUMENT', 'BIOMETRIC'
    
    -- Identifiers (hashed)
    entity_hash VARCHAR(255) UNIQUE,
    
    -- Attributes (JSONB)
    attributes JSONB,
    
    -- Metadata
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    screening_count INTEGER DEFAULT 1,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Identity Links (graph edges)
CREATE TABLE identity_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_entity_id UUID REFERENCES identity_entities(id),
    to_entity_id UUID REFERENCES identity_entities(id),
    link_type VARCHAR(50), -- 'OWNS', 'HAS_BIOMETRIC', 'SIMILAR_TO'
    confidence DECIMAL(5, 4),
    metadata JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Identity Conflicts
CREATE TABLE identity_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id),
    
    conflict_type VARCHAR(50),
    severity DECIMAL(5, 4),
    description TEXT,
    evidence_sources TEXT[],
    details JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlist Entries
CREATE TABLE watchlist_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50), -- 'SYNTHETIC', 'OPENSANCTIONS', 'INTERPOL'
    list_name VARCHAR(100),
    category VARCHAR(50),
    
    -- Entity data (hashed)
    name_hash VARCHAR(255),
    name_encrypted TEXT, -- Encrypted with proper key management
    aliases TEXT[],
    
    date_of_birth DATE,
    nationality VARCHAR(3),
    document_numbers TEXT[],
    
    reason TEXT,
    is_simulated BOOLEAN DEFAULT false,
    source_url TEXT,
    
    added_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlist Hits
CREATE TABLE watchlist_hits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id),
    watchlist_entry_id UUID REFERENCES watchlist_entries(id),
    
    match_confidence DECIMAL(5, 4),
    matched_fields TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evidence Contradictions
CREATE TABLE evidence_contradictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id),
    
    contradiction_type contradiction_type,
    severity DECIMAL(5, 4),
    description TEXT,
    evidence_sources TEXT[],
    details JSONB,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Events
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    screening_id UUID REFERENCES screenings(id),
    user_id UUID REFERENCES users(id),
    
    event_type VARCHAR(50),
    event_data JSONB,
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Blockchain Anchors (for audit trail)
CREATE TABLE blockchain_anchors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    record_type VARCHAR(50),
    record_id UUID,
    
    record_hash VARCHAR(255) NOT NULL,
    parent_hash VARCHAR(255),
    chain_id VARCHAR(100),
    
    -- Blockchain info (future)
    blockchain_tx_hash VARCHAR(255),
    blockchain_block_number BIGINT,
    
    anchored_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- System Statistics (aggregated)
CREATE TABLE system_statistics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE UNIQUE NOT NULL,
    
    total_screenings INTEGER DEFAULT 0,
    clear_count INTEGER DEFAULT 0,
    low_risk_count INTEGER DEFAULT 0,
    medium_risk_count INTEGER DEFAULT 0,
    high_risk_count INTEGER DEFAULT 0,
    critical_risk_count INTEGER DEFAULT 0,
    
    avg_processing_time_ms INTEGER,
    watchlist_hits INTEGER DEFAULT 0,
    contradictions_found INTEGER DEFAULT 0,
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Users
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_station ON users(station_id);
CREATE INDEX idx_users_active ON users(is_active);

-- Screenings
CREATE INDEX idx_screenings_officer ON screenings(officer_id);
CREATE INDEX idx_screenings_station ON screenings(station_id);
CREATE INDEX idx_screenings_status ON screenings(status);
CREATE INDEX idx_screenings_risk_level ON screenings(risk_level);
CREATE INDEX idx_screenings_date ON screenings(screening_started_at);
CREATE INDEX idx_screenings_doc_hash ON screenings(document_number_hash);

-- Documents
CREATE INDEX idx_documents_screening ON documents(screening_id);
CREATE INDEX idx_documents_number ON documents(document_number);
CREATE INDEX idx_documents_country ON documents(issuing_country);

-- MRZ
CREATE INDEX idx_mrz_screening ON mrz_records(screening_id);
CREATE INDEX idx_mrz_valid ON mrz_records(is_valid);

-- Forensics
CREATE INDEX idx_forensics_screening ON forensic_results(screening_id);
CREATE INDEX idx_forensics_tampering ON forensic_results(tampering_probability);

-- Face
CREATE INDEX idx_face_screening ON face_captures(screening_id);
CREATE INDEX idx_face_hash ON face_captures(face_hash);
CREATE INDEX idx_face_embedding ON face_captures(embedding_hash);

-- Identity
CREATE INDEX idx_identity_hash ON identity_entities(entity_hash);
CREATE INDEX idx_identity_type ON identity_entities(entity_type);
CREATE INDEX idx_identity_links_from ON identity_links(from_entity_id);
CREATE INDEX idx_identity_links_to ON identity_links(to_entity_id);

-- Watchlist
CREATE INDEX idx_watchlist_source ON watchlist_entries(source);
CREATE INDEX idx_watchlist_active ON watchlist_entries(is_active);
CREATE INDEX idx_watchlist_hits_screening ON watchlist_hits(screening_id);

-- Audit
CREATE INDEX idx_audit_screening ON audit_events(screening_id);
CREATE INDEX idx_audit_user ON audit_events(user_id);
CREATE INDEX idx_audit_date ON audit_events(created_at);

-- Blockchain
CREATE INDEX idx_blockchain_chain ON blockchain_anchors(chain_id);
CREATE INDEX idx_blockchain_hash ON blockchain_anchors(record_hash);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE screenings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE mrz_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE forensic_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE validation_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE face_captures ENABLE ROW LEVEL SECURITY;
ALTER TABLE face_verification_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_hits ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_contradictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE blockchain_anchors ENABLE ROW LEVEL SECURITY;

-- Users: Can see own profile, admins see all
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid() = auth_user_id OR EXISTS (
        SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role = 'ADMIN'
    ));

CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (auth.uid() = auth_user_id OR EXISTS (
        SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role = 'ADMIN'
    ));

-- Screenings: Officers see own, supervisors see station, admins see all
CREATE POLICY screenings_select ON screenings
    FOR SELECT
    USING (
        officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
        OR EXISTS (
            SELECT 1 FROM users u
            WHERE u.auth_user_id = auth.uid()
            AND (u.role IN ('SUPERVISOR', 'ADMIN') OR u.role = 'ANALYST')
        )
    );

CREATE POLICY screenings_insert ON screenings
    FOR INSERT
    WITH CHECK (
        officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY screenings_update ON screenings
    FOR UPDATE
    USING (
        officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
        OR EXISTS (
            SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN')
        )
    );

-- Documents, MRZ, OCR, Forensics, etc.: Follow screening access
CREATE POLICY documents_access ON documents
    FOR ALL
    USING (
        screening_id IN (
            SELECT id FROM screenings WHERE
            officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
            OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST'))
        )
    );

-- Similar policies for other tables (applying same logic)
CREATE POLICY mrz_access ON mrz_records FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

CREATE POLICY ocr_access ON ocr_results FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

CREATE POLICY forensics_access ON forensic_results FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

CREATE POLICY validation_access ON validation_results FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

CREATE POLICY face_captures_access ON face_captures FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

CREATE POLICY face_verification_access ON face_verification_results FOR ALL USING (
    screening_id IN (SELECT id FROM screenings WHERE officer_id IN (SELECT id FROM users WHERE auth_user_id = auth.uid())
    OR EXISTS (SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('SUPERVISOR', 'ADMIN', 'ANALYST')))
);

-- Watchlist: Analysts and above can read, admins can modify
CREATE POLICY watchlist_read ON watchlist_entries
    FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('ANALYST', 'SUPERVISOR', 'ADMIN')
    ));

CREATE POLICY watchlist_modify ON watchlist_entries
    FOR ALL
    USING (EXISTS (
        SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role = 'ADMIN'
    ));

-- Audit: Auditors and admins can read all
CREATE POLICY audit_read ON audit_events
    FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM users WHERE auth_user_id = auth.uid() AND role IN ('AUDITOR', 'ADMIN')
    ));

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_screenings_updated_at BEFORE UPDATE ON screenings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to aggregate daily statistics
CREATE OR REPLACE FUNCTION aggregate_daily_statistics(target_date DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO system_statistics (
        date,
        total_screenings,
        clear_count,
        low_risk_count,
        medium_risk_count,
        high_risk_count,
        critical_risk_count,
        watchlist_hits,
        contradictions_found,
        updated_at
    )
    SELECT
        target_date,
        COUNT(*),
        SUM(CASE WHEN risk_level = 'CLEAR' THEN 1 ELSE 0 END),
        SUM(CASE WHEN risk_level = 'LOW' THEN 1 ELSE 0 END),
        SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END),
        SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END),
        SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END),
        (SELECT COUNT(*) FROM watchlist_hits wh WHERE wh.screening_id IN (
            SELECT id FROM screenings WHERE DATE(screening_started_at) = target_date
        )),
        (SELECT COUNT(*) FROM evidence_contradictions ec WHERE ec.screening_id IN (
            SELECT id FROM screenings WHERE DATE(screening_started_at) = target_date
        )),
        NOW()
    FROM screenings
    WHERE DATE(screening_started_at) = target_date
    ON CONFLICT (date) DO UPDATE SET
        total_screenings = EXCLUDED.total_screenings,
        clear_count = EXCLUDED.clear_count,
        low_risk_count = EXCLUDED.low_risk_count,
        medium_risk_count = EXCLUDED.medium_risk_count,
        high_risk_count = EXCLUDED.high_risk_count,
        critical_risk_count = EXCLUDED.critical_risk_count,
        watchlist_hits = EXCLUDED.watchlist_hits,
        contradictions_found = EXCLUDED.contradictions_found,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SEED DATA (Initial setup)
-- ============================================================================

-- Insert default admin user (password: change_me_123)
-- Note: This should be updated after first login
INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at)
VALUES (
    uuid_generate_v4(),
    'admin@borderscreening.gov.in',
    crypt('change_me_123', gen_salt('bf')),
    NOW(),
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;

-- Create admin user profile
INSERT INTO users (auth_user_id, email, full_name, role, station_id, badge_number)
SELECT 
    id,
    'admin@borderscreening.gov.in',
    'System Administrator',
    'ADMIN',
    'HQ-001',
    'ADMIN-001'
FROM auth.users
WHERE email = 'admin@borderscreening.gov.in'
ON CONFLICT DO NOTHING;

-- Insert sample stations
INSERT INTO stations (code, name, location_city, location_state, location_country, station_type) VALUES
('DEL-AIR-01', 'Indira Gandhi International Airport', 'New Delhi', 'Delhi', 'IND', 'AIRPORT'),
('BOM-AIR-01', 'Chhatrapati Shivaji Maharaj International Airport', 'Mumbai', 'Maharashtra', 'IND', 'AIRPORT'),
('BLR-AIR-01', 'Kempegowda International Airport', 'Bengaluru', 'Karnataka', 'IND', 'AIRPORT'),
('MAA-AIR-01', 'Chennai International Airport', 'Chennai', 'Tamil Nadu', 'IND', 'AIRPORT'),
('CCU-AIR-01', 'Netaji Subhas Chandra Bose International Airport', 'Kolkata', 'West Bengal', 'IND', 'AIRPORT'),
('ATT-LND-01', 'Attari Land Port', 'Attari', 'Punjab', 'IND', 'LAND_BORDER'),
('WAG-LND-01', 'Wagah Border', 'Attari', 'Punjab', 'IND', 'LAND_BORDER')
ON CONFLICT DO NOTHING;

-- Insert synthetic watchlist entries (for demo)
INSERT INTO watchlist_entries (source, list_name, category, name_hash, name_encrypted, reason, is_simulated, is_active)
VALUES
('SYNTHETIC', 'DEMO_WATCHLIST', 'TERRORISM', md5('DEMO TERRORIST ALPHA'), 'DEMO TERRORIST ALPHA', 'SIMULATED - Demo entry for testing', true, true),
('SYNTHETIC', 'DEMO_WATCHLIST', 'SANCTIONS', md5('TEST SANCTIONS BETA'), 'TEST SANCTIONS BETA', 'SIMULATED - Demo sanctions entry', true, true),
('SYNTHETIC', 'DEMO_WATCHLIST', 'FRAUD', md5('SAMPLE FRAUD GAMMA'), 'SAMPLE FRAUD GAMMA', 'SIMULATED - Demo fraud pattern', true, true),
('SYNTHETIC', 'DEMO_WATCHLIST', 'WANTED', md5('DEMO WANTED DELTA'), 'DEMO WANTED DELTA', 'SIMULATED - Demo wanted person', true, true)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- STORAGE BUCKETS (Supabase Storage)
-- ============================================================================

-- Note: These need to be created via Supabase dashboard or API
-- CREATE BUCKET IF NOT EXISTS document_images (private);
-- CREATE BUCKET IF NOT EXISTS face_captures (private);

-- ============================================================================
-- VIEWS FOR ANALYTICS
-- ============================================================================

CREATE OR REPLACE VIEW screening_summary AS
SELECT
    s.id,
    s.screening_started_at,
    s.risk_level,
    s.risk_score,
    s.recommended_action,
    s.officer_decision,
    u.full_name AS officer_name,
    st.name AS station_name,
    (SELECT COUNT(*) FROM evidence_contradictions WHERE screening_id = s.id) AS contradiction_count,
    (SELECT COUNT(*) FROM watchlist_hits WHERE screening_id = s.id) AS watchlist_hit_count
FROM screenings s
LEFT JOIN users u ON s.officer_id = u.id
LEFT JOIN stations st ON s.station_id = st.id;

CREATE OR REPLACE VIEW high_risk_screenings AS
SELECT * FROM screening_summary
WHERE risk_level IN ('HIGH', 'CRITICAL')
ORDER BY screening_started_at DESC;

-- ============================================================================
-- SCHEDULED JOBS (pg_cron)
-- ============================================================================

-- Aggregate statistics daily at midnight
SELECT cron.schedule(
    'aggregate-daily-stats',
    '0 0 * * *',
    $$SELECT aggregate_daily_statistics(CURRENT_DATE - INTERVAL '1 day')$$
);

-- ============================================================================
-- GRANTS (Adjust based on your Supabase setup)
-- ============================================================================

-- Grant authenticated users access to tables
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;

-- ============================================================================
-- COMPLETION
-- ============================================================================

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version VARCHAR(20) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_versions (version, description) VALUES
('1.0.0', 'Initial schema with all tables, RLS policies, and seed data');

-- Done!
SELECT 'Database schema created successfully!' AS status;
