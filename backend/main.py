"""
Border Screening API — FastAPI Application Entry Point.

AI-Based Border Document Screening System
"""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("border-screening")

try:
    from app.core.database import engine, Base, USING_SUPABASE, SupabaseConnectionError
except Exception as exc:  # pragma: no cover - startup guard
    print(f"\n{exc}\n", file=sys.stderr)
    raise SystemExit(1) from exc

from app.api.v1.router import api_router
from app.services.storage.supabase_storage import supabase_storage

# Create the ORM schema in Supabase Postgres if it does not exist yet.
Base.metadata.create_all(engine)
logger.info(
    "Persistence: %s",
    "Supabase PostgreSQL" if USING_SUPABASE else "local SQLite (REQUIRE_SUPABASE=false)",
)

# Ensure the private Storage buckets exist before the first upload arrives.
if supabase_storage.enabled:
    supabase_storage.ensure_buckets()
    logger.info(
        "Object storage: Supabase buckets '%s' and '%s'.",
        settings.STORAGE_DOCUMENT_BUCKET,
        settings.STORAGE_FACE_BUCKET,
    )
else:
    logger.warning(
        "Object storage: Supabase Storage is NOT configured — document images "
        "will stay on local disk. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
    )

# ── Refuse to boot a production instance with development-grade secrets ──────
_security_problems = settings.validate_runtime_security()
if _security_problems:
    if settings.is_production:
        for _p in _security_problems:
            logger.critical("SECURITY: %s", _p)
        raise SystemExit(
            "Refusing to start in production with insecure configuration. "
            "Resolve the SECURITY items above."
        )
    for _p in _security_problems:
        logger.warning("Insecure for production: %s", _p)

app = FastAPI(
    title="Border Document Screening API",
    description="AI-powered document verification, forgery detection, and face matching for border checkpoints.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    # Interactive docs enumerate every endpoint and schema; keep them off in prod.
    openapi_url=None if settings.is_production else "/openapi.json",
)

from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Return unhandled server errors as JSON so the browser can actually read them.

    Without this handler, an unhandled exception is turned into a 500 by
    Starlette's ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware. That
    response therefore carries no Access-Control-Allow-Origin header, so the
    browser blocks it and reports a generic network failure — the frontend showed
    "Failed to fetch" with no indication that the server had actually replied
    with an error, which made real backend bugs look like connectivity problems.

    Registering the handler here means the response is generated inside the
    middleware stack and picks up CORS headers on the way out.
    """
    logger.error(
        "Unhandled error on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True,
    )
    detail = f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail})


from app.core.middleware import RateLimitMiddleware

# Rate limiting middleware (120 requests per minute per IP)
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

# CORS middleware - supports explicit origins and any *.vercel.app domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

# The scratch directory holds in-flight uploads while the CV/OCR models read
# them from disk. It is NOT web-exposed.
#
# There used to be `app.mount("/uploads", StaticFiles(...))` here, which served
# that whole directory with no authentication — every traveller's passport scan,
# selfie and undeleted face crop was downloadable by anyone who could guess or
# list a filename. Images now reach the browser only as short-lived Supabase
# signed URLs minted per request in `_scan_to_response`.
os.makedirs(os.path.abspath(settings.UPLOAD_DIR), exist_ok=True)

# Include API routes
app.include_router(api_router)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint — API info."""
    return {
        "service": "Border Document Screening API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "persistence": "supabase-postgres" if USING_SUPABASE else "local-sqlite",
        "object_storage": "supabase-storage" if supabase_storage.enabled else "local-disk",
    }
