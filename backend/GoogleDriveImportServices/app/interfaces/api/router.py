from fastapi import APIRouter

from app.interfaces.api.v1.routes import google_drive_routes, health_routes

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_routes.router, tags=["health"])
api_router.include_router(google_drive_routes.router, tags=["google-drive"])
