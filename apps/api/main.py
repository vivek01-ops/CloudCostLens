"""FastAPI application factory for CloudCostLens."""

from __future__ import annotations

from core.config import get_settings
from core.logging import configure_logging, get_logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routers import health, meta

log = get_logger("apps.api.main")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_runtime()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.version,
        description="CloudCostLens — AWS cost intelligence and optimization API.",
        docs_url="/docs" if settings.debug or not settings.is_production else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(meta.router, prefix=settings.api_base_path)

    @app.exception_handler(Exception)
    async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled exception", error=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": settings.version, "docs": "/docs"}

    return app


app = create_app()