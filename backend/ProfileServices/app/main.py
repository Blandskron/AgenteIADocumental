from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config.logging import configure_logging
from app.config.readiness import check_dependencies
from app.config.settings import Settings, get_settings
from app.infrastructure.database.connection import Database
from app.interfaces.api.router import api_router
from app.interfaces.api.body_limit import ProfileBodyLimit
from app.shared.errors import AppError, ConflictError


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url, settings.db_pool_min_size,
                        settings.db_pool_max_size, settings.db_timeout_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        try:
            try:
                database.open()
                with database.session() as session:
                    check_dependencies(settings, session)
            except Exception:
                raise RuntimeError("Profile dependencies are unavailable.") from None
            yield
        finally:
            database.close()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(ProfileBodyLimit)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"],
    )
    app.include_router(api_router)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(RequestValidationError, invalid_request_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    return app


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Profile operation failed."})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Profile changed. Reload it before saving again."})


async def invalid_request_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    allowed = {"body", "query", "path", "expected_version", "email", "phone_number", "profile_picture_url", "additional_info", "file"}
    errors = [{"loc": [part if type(part) is int or part in allowed else "field" for part in error["loc"]],
               "msg": "Invalid profile value.", "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Profile write conflicts with persisted data."})


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "Profile persistence is unavailable."})
