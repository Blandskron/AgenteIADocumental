from fastapi import APIRouter, Depends, Response

from app.config.security import require_authenticated_user
from app.interfaces.api.v1.routes import health_routes, profile_routes

def prevent_profile_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


api_router = APIRouter()
api_router.include_router(health_routes.router, prefix="/api/v1", tags=["health"])
api_router.include_router(
    profile_routes.router,
    prefix="/api/v1",
    tags=["profile"],
    dependencies=[Depends(require_authenticated_user), Depends(prevent_profile_cache)],
)
