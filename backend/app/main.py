"""FastAPI application factory, lifecycle, middleware, and Phase 1 routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from app.config import Settings, get_settings
from app.db.client import close_database_connection, connect_to_database
from app.documents.routes import router as documents_router
from app.redaction.routes import router as redaction_router
from app.audit.routes import router as audit_router
from app.batch.routes import router as batch_router
from app.review.routes import router as review_router
from app.sharing.routes import router as sharing_router
from app.intelligence.routes import router as intelligence_router
from app.batch.job_runner import batch_worker
from app.storage.temp_manager import periodic_cleanup, prepare_storage_root


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    await connect_to_database(settings)
    prepare_storage_root(settings.temp_job_dir)
    cleanup_stop = asyncio.Event()
    cleanup_task = asyncio.create_task(
        periodic_cleanup(
            settings.temp_job_dir,
            settings.temp_job_ttl_seconds,
            settings.temp_cleanup_interval_seconds,
            cleanup_stop,
        ),
        name="medvault-temp-cleanup",
    )
    batch_stop = asyncio.Event()
    batch_task = asyncio.create_task(batch_worker(settings, batch_stop), name="medvault-batch-worker")
    try:
        yield
    finally:
        cleanup_stop.set()
        batch_stop.set()
        await cleanup_task
        await batch_task
        await close_database_connection()


def create_app(*, settings: Settings | None = None, manage_database: bool = True) -> FastAPI:
    """Build an application; tests may supply settings and an external test database."""

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.debug,
        version="2.0.0",
        lifespan=lifespan if manage_database else None,
    )
    application.state.settings = resolved_settings
    application.dependency_overrides[get_settings] = lambda: resolved_settings

    wildcard = "*" in resolved_settings.cors_origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False if wildcard else True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
    )
    application.include_router(auth_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(documents_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(redaction_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(audit_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(batch_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(review_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(sharing_router, prefix=resolved_settings.api_v1_prefix)
    application.include_router(intelligence_router, prefix=resolved_settings.api_v1_prefix)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": resolved_settings.app_name}

    return application


app = create_app()
