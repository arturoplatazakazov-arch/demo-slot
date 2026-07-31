from fastapi import APIRouter, Depends

from app.api.security import require_access_code
from app.api.v1.catalog import router as catalog_router
from app.api.v1.feature import router as feature_router
from app.api.v1.session import router as session_router
from app.api.v1.spin import router as spin_router

# The access-code gate applies to every v1 route; it's a no-op when no code is
# configured (local dev / tests), so nothing changes there.
api_v1_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_access_code)])
api_v1_router.include_router(session_router, tags=["session"])
api_v1_router.include_router(spin_router, tags=["spin"])
api_v1_router.include_router(feature_router, tags=["feature"])
api_v1_router.include_router(catalog_router, tags=["catalog"])

__all__ = ["api_v1_router"]
