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

app = FastAPI(
    title="Border Document Screening API",
    description="AI-powered document verification, forgery detection, and face matching for border checkpoints.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.core.middleware import RateLimitMiddleware

# Rate limiting middleware (120 requests per minute per IP)
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
import os

# Scratch directory for in-flight uploads. Document images themselves live in
# private Supabase Storage and are served to the browser via signed URLs, so
# this is only mounted for legacy records created before the storage migration.
uploads_dir = os.path.abspath(settings.UPLOAD_DIR)
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

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
