"""
Migration script: adds new fraud intelligence columns to scan_records, face_results, and risk_scores.
"""

from app.core.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("[MIGRATION] Adding fraud intelligence columns...")
        
        # scan_records columns
        conn.execute(text("ALTER TABLE scan_records ADD COLUMN IF NOT EXISTS chip_pki_status VARCHAR(50) DEFAULT 'AUTHENTIC_VALID';"))
        conn.execute(text("ALTER TABLE scan_records ADD COLUMN IF NOT EXISTS canonical_hash VARCHAR(64);"))
        
        # face_results columns
        conn.execute(text("ALTER TABLE face_results ADD COLUMN IF NOT EXISTS face_embedding JSONB;"))
        conn.execute(text("ALTER TABLE face_results ADD COLUMN IF NOT EXISTS continuity_links JSONB;"))
        
        # risk_scores columns
        conn.execute(text("ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS contradiction_matrix JSONB;"))
        conn.execute(text("ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS identity_graph_summary JSONB;"))
        conn.execute(text("ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS fraud_patterns_matched JSONB;"))
        conn.execute(text("ALTER TABLE risk_scores ADD COLUMN IF NOT EXISTS canonical_hash VARCHAR(64);"))
        
        conn.commit()
        print("[MIGRATION SUCCESS] All fraud intelligence columns added successfully.")

if __name__ == "__main__":
    migrate()
