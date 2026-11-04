from fastapi import APIRouter, Depends

from app.config.security import require_authenticated_user
from app.interfaces.api.v1.routes import health_routes, library_routes

api_router = APIRouter()
api_router.include_router(health_routes.router, prefix="/api/v1", tags=["health"])
api_router.include_router(
    library_routes.router,
    prefix="/api/v1",
    tags=["document-library"],
    dependencies=[Depends(require_authenticated_user)],
)
