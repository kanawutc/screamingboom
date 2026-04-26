"""API v1 router — aggregates all sub-routers."""

import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession, RedisClient
from app.api.v1.crawls import router as crawls_router
from app.api.v1.issues import router as issues_router
from app.api.v1.projects import router as projects_router
from app.api.v1.urls import router as urls_router
from app.api.v1.comparison import router as comparison_router
from app.api.v1.extraction_rules import router as extraction_rules_router
from app.api.v1.custom_rules import router as custom_rules_router
from app.api.v1.schedules import router as schedules_router

logger = structlog.get_logger(__name__)

v1_router = APIRouter()

# Include sub-routers
v1_router.include_router(comparison_router)
v1_router.include_router(projects_router)
v1_router.include_router(crawls_router)
v1_router.include_router(urls_router)
v1_router.include_router(issues_router)
v1_router.include_router(extraction_rules_router)
v1_router.include_router(custom_rules_router)
v1_router.include_router(schedules_router)


@v1_router.get("/health", tags=["health"])
async def health_check(db: DbSession, redis: RedisClient) -> dict[str, object]:
    """Health check endpoint. Returns status of all dependent services."""
    services: dict[str, str] = {}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = "ok"
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        services["database"] = "error"

    # Check Redis
    try:
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        services["redis"] = "error"

    status = "healthy" if all(v == "ok" for v in services.values()) else "degraded"

    return {
        "status": status,
        "version": "0.1.0",
        "services": services,
    }
