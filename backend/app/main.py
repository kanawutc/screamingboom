"""FastAPI application factory with lifespan management."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import create_db_engine, dispose_db_engine
from app.api.deps import init_redis, close_redis
from app.api.v1.router import v1_router
from app.websocket.manager import init_broadcaster, shutdown_broadcaster

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle: startup and shutdown."""
    configure_logging()
    logger.info("Starting SEO Spider backend", version="0.1.0")

    # Startup: initialize DB engine and Redis
    await create_db_engine()
    logger.info("Database connection pool created")
    redis = await init_redis()
    logger.info("Redis client initialized")

    # Initialize WebSocket broadcaster
    init_broadcaster(redis)
    logger.info("WebSocket broadcaster initialized")

    yield

    # Shutdown: close connections
    await shutdown_broadcaster()
    logger.info("WebSocket broadcaster shut down")
    await close_redis()
    logger.info("Redis client closed")
    await dispose_db_engine()
    logger.info("SEO Spider backend shutting down")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SEO Spider API",
        description="Self-hosted Screaming Frog SEO Spider clone",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom exception handlers
    register_exception_handlers(app)

    # Include API routers
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_application()
