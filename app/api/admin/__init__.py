from fastapi import APIRouter

from app.api.admin.builder import router as admin_builder_router
from app.api.admin.calibration import router as admin_calibration_router
from app.api.admin.router import router as admin_config_router

api_admin_router = APIRouter(prefix="/api/admin")
api_admin_router.include_router(admin_config_router, tags=["admin"])
api_admin_router.include_router(admin_builder_router, tags=["builder"])
api_admin_router.include_router(admin_calibration_router, tags=["calibration"])

__all__ = ["api_admin_router"]
