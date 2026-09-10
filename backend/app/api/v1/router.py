"""
API v1 router — aggregates all route modules.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.scans import router as scans_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as health_router
from app.api.v1.audit import router as audit_router
from app.api.v1.face import router as face_router
from app.api.v1.supervisor import router as supervisor_router
from app.api.v1.ws import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(scans_router)
api_router.include_router(dashboard_router)
api_router.include_router(health_router)
api_router.include_router(audit_router)
api_router.include_router(face_router)
api_router.include_router(supervisor_router)
api_router.include_router(ws_router)
