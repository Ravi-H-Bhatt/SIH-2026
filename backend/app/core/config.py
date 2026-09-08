"""
Core configuration module.
Loads settings from .env file using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Database — Supabase PostgreSQL is the single source of truth.
    # -------------------------------------------------------------------------
    # Either provide the full connection string (Supabase Dashboard →
    # Project Settings → Database → Connection string → URI):
    #     DATABASE_URL=postgresql://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres
    # ...or just set SUPABASE_DB_PASSWORD and the URL is derived from SUPABASE_URL.
    DATABASE_URL: str = ""
    SUPABASE_DB_PASSWORD: Optional[str] = None
    SUPABASE_DB_HOST: Optional[str] = None  # override pooler host if needed
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_USER: Optional[str] = None

    # When True the app refuses to boot on anything other than Supabase Postgres
    # instead of silently degrading to a throwaway local SQLite file.
    REQUIRE_SUPABASE: bool = True

    # JWT Auth
    SECRET_KEY: str = "sih26188-border-ai-secret-key-change-in-production-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"

    # -------------------------------------------------------------------------
    # Object storage — Supabase Storage is the single source of truth for images.
    # -------------------------------------------------------------------------
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    STORAGE_DOCUMENT_BUCKET: str = "document-images"
    STORAGE_FACE_BUCKET: str = "face-captures"
    STORAGE_MAX_FILE_SIZE_MB: int = 15
    STORAGE_SIGNED_URL_TTL_SECONDS: int = 3600

    # Scratch space only. Uploads are streamed to a temp file so the CV/OCR
    # models can read them from disk, then deleted once pushed to Supabase.
    UPLOAD_DIR: str = "./uploads"
    KEEP_LOCAL_UPLOAD_COPY: bool = False

    # -------------------------------------------------------------------------
    # Checkpoint geolocation — used for the operations map.
    # -------------------------------------------------------------------------
    CHECKPOINT_NAME: str = "IGI Airport Terminal 3"
    CHECKPOINT_LATITUDE: float = 28.5562
    CHECKPOINT_LONGITUDE: float = 77.1000

    # -------------------------------------------------------------------------
    # Google Cloud Vision API
    # -------------------------------------------------------------------------
    # Authentication — NEVER expose these to the browser or Next.js frontend.
    # Preferred: set GOOGLE_APPLICATION_CREDENTIALS=/abs/path/service-account.json
    # The Google Auth library picks this up automatically (ADC).
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # path, not the JSON content

    # Optional API-key mode — service-account / ADC is strongly preferred.
    GOOGLE_VISION_API_KEY: Optional[str] = None

    # OCR provider selection
    # Values: "google_vision" | "local"
    OCR_PROVIDER: str = "local"
    OCR_FALLBACK_ENABLED: bool = True

    # Local OCR engine chain (tried in order, first one available wins).
    # "tesseract" works on macOS/Linux/Windows, "apple_vision" is macOS-only
    # and needs pyobjc, "windows" is the legacy WinRT engine.
    OCR_LOCAL_ENGINES: str = "tesseract,apple_vision,windows"
    TESSERACT_CMD: Optional[str] = None  # explicit binary path if not on PATH

    # Vision cost / safety controls
    VISION_MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    VISION_REQUEST_TIMEOUT_SECONDS: float = 30.0
    VISION_MAX_RETRIES: int = 2

    # -------------------------------------------------------------------------
    # Blockchain audit anchor (optional).
    #
    # The SHA-256 canonical evidence hash is ALWAYS computed and stored in
    # Supabase — that is what proves the record was not altered. Anchoring adds
    # an independent public timestamp so the proof does not rely on us also
    # controlling the database. Entirely optional.
    # -------------------------------------------------------------------------
    BLOCKCHAIN_ANCHOR_ENABLED: bool = False

    # Google Cloud Blockchain RPC API (never expose to the browser).
    GOOGLE_BLOCKCHAIN_API_KEY: Optional[str] = None
    GOOGLE_BLOCKCHAIN_RPC_URL: Optional[str] = None

    # Submitting a transaction costs gas. Without a funded key the service runs
    # in read-only mode: it can verify anchors but not create new ones.
    BLOCKCHAIN_ANCHOR_PRIVATE_KEY: Optional[str] = None
    BLOCKCHAIN_ANCHOR_FROM_ADDRESS: Optional[str] = None
    BLOCKCHAIN_CHAIN_ID: int = 11155111  # Ethereum Sepolia testnet

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Dev bypass (set to True to skip JWT auth and use demo token)
    BYPASS_AUTH: bool = False

    # Admin approval settings
    AUTO_APPROVE_USERS: bool = True
    REQUIRE_ADMIN_APPROVAL: bool = False

    # Admin bootstrap (used by init_admin.py only)
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_FULL_NAME: str = "System Administrator"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def supabase_project_ref(self) -> Optional[str]:
        """Extracts the project ref from https://<ref>.supabase.co."""
        if not self.SUPABASE_URL:
            return None
        host = self.SUPABASE_URL.replace("https://", "").replace("http://", "").strip("/")
        ref = host.split(".")[0]
        return ref or None

    @property
    def local_ocr_engines(self) -> List[str]:
        return [e.strip().lower() for e in self.OCR_LOCAL_ENGINES.split(",") if e.strip()]

    @property
    def supabase_storage_configured(self) -> bool:
        """Supabase Storage needs the project URL plus the service-role key."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_ROLE_KEY)

    def resolved_database_url(self) -> str:
        """
        Returns a SQLAlchemy-ready Supabase PostgreSQL URL.

        Resolution order:
          1. DATABASE_URL when it is already a postgres:// URL.
          2. Derived from SUPABASE_URL + SUPABASE_DB_PASSWORD.
          3. Whatever DATABASE_URL contains (e.g. sqlite://) as a last resort.
        """
        raw = (self.DATABASE_URL or "").strip()
        placeholder = any(tok in raw for tok in ("[YOUR", "YOUR_SUPABASE", "YOUR-PASSWORD"))

        if raw.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")) and not placeholder:
            return raw.replace("postgres://", "postgresql://").replace(
                "postgresql://", "postgresql+psycopg://", 1
            )

        ref = self.supabase_project_ref
        if ref and self.SUPABASE_DB_PASSWORD:
            from urllib.parse import quote_plus

            pwd = quote_plus(self.SUPABASE_DB_PASSWORD)
            host = self.SUPABASE_DB_HOST or f"db.{ref}.supabase.co"
            user = self.SUPABASE_DB_USER or (
                "postgres" if host.startswith("db.") else f"postgres.{ref}"
            )
            return (
                f"postgresql+psycopg://{user}:{pwd}@{host}:{self.SUPABASE_DB_PORT}/postgres"
                "?sslmode=require"
            )

        return "" if placeholder else raw

    @property
    def google_vision_configured(self) -> bool:
        """True if Google Vision credentials appear to be configured."""
        return bool(
            self.GOOGLE_APPLICATION_CREDENTIALS or self.GOOGLE_VISION_API_KEY
        )

    @property
    def blockchain_rpc_endpoint(self) -> Optional[str]:
        """
        Full RPC URL including the API key.

        Google's Blockchain RPC API authenticates with `?key=<API_KEY>` appended
        to the endpoint URL, so we assemble it here rather than storing the
        secret inside the URL in .env.
        """
        if not self.GOOGLE_BLOCKCHAIN_RPC_URL:
            return None
        url = self.GOOGLE_BLOCKCHAIN_RPC_URL.strip()
        if "YOUR_PROJECT" in url:
            return None
        if not self.GOOGLE_BLOCKCHAIN_API_KEY:
            return url
        joiner = "&" if "?" in url else "?"
        return f"{url}{joiner}key={self.GOOGLE_BLOCKCHAIN_API_KEY}"

    @property
    def blockchain_can_write(self) -> bool:
        """On-chain writes need a funded signing key on top of RPC access."""
        return bool(
            self.BLOCKCHAIN_ANCHOR_ENABLED
            and self.blockchain_rpc_endpoint
            and self.BLOCKCHAIN_ANCHOR_PRIVATE_KEY
            and self.BLOCKCHAIN_ANCHOR_FROM_ADDRESS
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow extra fields so the .env can have additional keys without crashing
        extra = "ignore"


settings = Settings()
