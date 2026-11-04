from fastapi import APIRouter, Depends

from app.config.security import require_authenticated_user
from app.interfaces.api.v1.routes import document_routes, health_routes

api_router = APIRouter()
api_router.include_router(health_routes.router, prefix="/api/v1", tags=["health"])
api_router.include_router(
    document_routes.router,
    prefix="/api/v1/documents",
    tags=["documents"],
    dependencies=[Depends(require_authenticated_user)],
)
