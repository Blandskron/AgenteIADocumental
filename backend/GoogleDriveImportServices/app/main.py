from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config.logging import configure_logging
from app.config.readiness import check_dependencies
from app.config.settings import Settings, get_settings
from app.infrastructure.database.connection import Database
from app.interfaces.api.router import api_router
from app.interfaces.api.credential_middleware import CredentialMiddleware
from app.shared.errors import ImportConnectionConflict, ImportSourceConflict, DriveConflictError, ReauthorizationRequired, AppError, ExternalServiceError, GoogleDriveError, NotFoundError, ValidationError


def create_app(settings: Settings | None = None):
    settings = settings or get_settings()
    database = Database(settings.database_url, settings.db_pool_min_size, settings.db_pool_max_size, settings.db_timeout_seconds)

    @asynccontextmanager
    async def lifespan(app):
        configure_logging(settings.log_level)
        try:
            try:
                database.open()
                with database.session() as session:
                    check_dependencies(settings, session)
            except Exception:
                raise RuntimeError("Drive dependencies are unavailable.") from None
            yield
        finally:
            database.close()

    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    app.state.database = database
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(CredentialMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    app.include_router(api_router)
    for kind, code, detail in ((DriveConflictError,409,"Drive operation changed or is busy."),
                              (ReauthorizationRequired,409,"Google Drive authorization must be renewed."),
                              (NotFoundError,404,"Google Drive resource not found."),
                              (ValidationError,400,"Invalid Google Drive request."),
                              (GoogleDriveError,502,"Google Drive provider operation failed."),
                              (ExternalServiceError,502,"Document ingestion is unavailable."),
                              (AppError,500,"Google Drive operation failed."),
                              (IntegrityError,409,"Drive operation conflicts with stored data."),
                              (SQLAlchemyError,503,"Drive persistence is unavailable."),
                              (Exception,500,"Google Drive operation failed.")):
        def handler(request, exc, code=code, detail=detail):
            return JSONResponse(status_code=code, content={"detail": detail})
        app.add_exception_handler(kind, handler)
    app.add_exception_handler(ImportConnectionConflict, import_connection_conflict)
    app.add_exception_handler(ImportSourceConflict, import_source_conflict)
    app.add_exception_handler(RequestValidationError, invalid_request)
    return app


async def invalid_request(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid Google Drive request values."})


async def import_source_conflict(request, exc):
    return JSONResponse(status_code=409, content={"code": "import_source_conflict", "detail": "Selected Drive files were already uploaded or require review."})


async def import_connection_conflict(request, exc):
    return JSONResponse(status_code=409, content={"code": "import_connection_changed", "detail": "Reload the current Google Drive connection before starting a new import."})
