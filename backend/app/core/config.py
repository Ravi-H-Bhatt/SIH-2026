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
    #
    # This default is a DEVELOPMENT placeholder and is rejected at startup when
    # ENVIRONMENT=production (see `validate_runtime_security`). It used to be a
    # silent fallback, which meant a deployed instance signed tokens with a value
    # published in this repo — anyone could mint an admin token.
    SECRET_KEY: str = "dev-only-insecure-key-override-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"

    # -------------------------------------------------------------------------
    # Google Sign-In (brokered through Supabase Auth)
    # -------------------------------------------------------------------------
    # The browser runs the Google OAuth dance against Supabase Auth and receives
    # a Supabase access token. It posts that to POST /api/v1/auth/google, and the
    # backend verifies it server-side against Supabase's /auth/v1/user endpoint
    # before issuing our own application JWT.
    #
    # Verifying via Supabase's own endpoint (rather than locally decoding the
    # token) means we do not have to track whether the project signs with a
    # shared HS256 secret or a rotating asymmetric key.
    GOOGLE_AUTH_ENABLED: bool = True

    # Comma-separated list of email domains permitted to sign in with Google.
    # Empty means any domain may *register*, but the account still lands
    # unapproved and an admin must grant access. For a real deployment restrict
    # this to your agency domain, e.g. "nic.in,gov.in".
    GOOGLE_ALLOWED_EMAIL_DOMAINS: str = ""

    # Role assigned to a brand-new Google account. Never make this "admin".
    GOOGLE_DEFAULT_ROLE: str = "officer"

    # -------------------------------------------------------------------------
    # Superadmin allow-list
    # -------------------------------------------------------------------------
    # Comma-separated emails that are granted the admin role and approved
    # automatically, whichever way they sign in (password or Google). This is the
    # bootstrap owner account so you are never locked out of your own deployment.
    #
    # Keep it short and treat it like a credential: anyone who controls one of
    # these mailboxes controls the system. Everything else must be approved from
    # the admin console.
    ADMIN_EMAILS: str = ""

    # Google accounts must be approved by an admin before they can do anything,
    # independent of AUTO_APPROVE_USERS. Self-service Google sign-in with
    # auto-approval would let anyone with a Google account into a border system.
    GOOGLE_REQUIRE_ADMIN_APPROVAL: bool = True

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

    # -------------------------------------------------------------------------
    # Watchlist / sanctions screening
    # -------------------------------------------------------------------------
    OPENSANCTIONS_ENABLED: bool = False
    OPENSANCTIONS_API_KEY: Optional[str] = None
    OPENSANCTIONS_API_URL: str = "https://api.opensanctions.org"
    OPENSANCTIONS_DATASET: str = "default"
    OPENSANCTIONS_TIMEOUT_SECONDS: float = 12.0
    # Candidate scores below this are discarded. OpenSanctions returns weak
    # partial matches by design, and surfacing them would bury real hits.
    OPENSANCTIONS_MATCH_THRESHOLD: float = 0.70

    SYNTHETIC_WATCHLIST_ENABLED: bool = True
    INTERPOL_ENABLED: bool = False

    # -------------------------------------------------------------------------
    # Biometric thresholds
    # -------------------------------------------------------------------------
    # These were previously present in .env but declared nowhere, so
    # pydantic-settings discarded them (extra="ignore") and the services used
    # hardcoded constants instead. Editing .env had no effect on behaviour.
    #
    # ── Biometric thresholds ────────────────────────────────────────────────
    #
    # Every threshold below is a RAW SFace cosine similarity in [-1, 1]. The
    # service reports the raw cosine and compares it directly against these
    # numbers. There is no rescaling, no calibration curve and no remap.
    #
    # History: this used to hold FACE_SIMILARITY_THRESHOLD=0.70 alongside
    # FACE_CROSS_DOMAIN_COSINE_THRESHOLD=0.30, and face_service mapped any
    # cosine >= 0.30 onto the range [0.70, 0.99] before comparing it against
    # 0.70. That made the comparison vacuous — every cosine above 0.30 passed,
    # and the officer-facing "70.3% vs 70% threshold" readout was arithmetic
    # applied to itself. An unrelated selfie scored raw 0.307 and cleared.
    #
    # FACE_MATCH_COSINE_THRESHOLD: 1:1 verification (document portrait vs live
    # capture). 0.363 is SFace's published same-domain operating point and is
    # the floor enforced in code — see face_service.MIN_SAFE_COSINE_THRESHOLD.
    FACE_MATCH_COSINE_THRESHOLD: float = 0.363

    # 1:N identity-graph / face-search linkage. Deliberately STRICTER than the
    # 1:1 threshold: a 1:N search over N stored encounters accumulates
    # false-match probability with N, so the per-comparison bar must be higher
    # to hold the overall false-link rate down. Previously 0.62 applied to a
    # (cos+1)/2 rescale, which corresponded to a raw cosine of just 0.24 —
    # looser than 1:1 despite a comment claiming the opposite.
    FACE_IDENTITY_MATCH_THRESHOLD: float = 0.50

    # Minimum YuNet detector confidence for a detection to be usable as
    # evidence. Detections below this are discarded rather than compared.
    FACE_QUALITY_THRESHOLD: float = 0.6

    # Anti-spoofing: minimum FFT high/low frequency energy ratio and edge
    # variance for a capture to be accepted as live.
    LIVENESS_MIN_FREQ_RATIO: float = 0.003
    LIVENESS_MIN_EDGE_VARIANCE: float = 10.0

    # -------------------------------------------------------------------------
    # Forensics & validation
    # -------------------------------------------------------------------------
    FORENSICS_ELA_QUALITY: int = 95
    FORENSICS_TAMPERING_THRESHOLD: float = 0.60
    VALIDATION_STRICT_MODE: bool = True
    VALIDATION_ICAO_COMPLIANCE: bool = True

    LOG_LEVEL: str = "INFO"

    # Admin bootstrap (used by init_admin.py only)
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_FULL_NAME: str = "System Administrator"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in ("production", "prod")

    @property
    def admin_emails(self) -> List[str]:
        return [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

    def is_superadmin_email(self, email: Optional[str]) -> bool:
        """True when `email` is on the bootstrap admin allow-list."""
        if not email:
            return False
        return email.strip().lower() in self.admin_emails

    @property
    def google_allowed_domains(self) -> List[str]:
        return [
            d.strip().lower().lstrip("@")
            for d in self.GOOGLE_ALLOWED_EMAIL_DOMAINS.split(",")
            if d.strip()
        ]

    @property
    def supabase_auth_configured(self) -> bool:
        """Google sign-in needs the project URL plus the anon key to verify tokens."""
        return bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY)

    def validate_runtime_security(self) -> List[str]:
        """
        Returns a list of fatal misconfigurations for a production boot.

        Called from main.py. In production these abort startup; in development
        they are logged as warnings so local work is not blocked.
        """
        problems: List[str] = []

        if self.SECRET_KEY == "dev-only-insecure-key-override-in-production":
            problems.append(
                "SECRET_KEY is still the development placeholder. Generate one with "
                "`python -c \"import secrets; print(secrets.token_urlsafe(64))\"` "
                "and set it in the environment."
            )
        elif len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY is shorter than 32 characters.")

        if self.BYPASS_AUTH:
            problems.append("BYPASS_AUTH=true must never be enabled outside local development.")

        if self.DEBUG:
            problems.append("DEBUG=true leaks stack traces; set DEBUG=false in production.")

        if any(o == "*" for o in self.cors_origins_list):
            problems.append("CORS_ORIGINS contains '*', which defeats credentialed CORS.")

        if self.AUTO_APPROVE_USERS:
            problems.append(
                "AUTO_APPROVE_USERS=true lets any self-registered account act immediately. "
                "Set it to false and approve users from the admin console."
            )

        return problems

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
