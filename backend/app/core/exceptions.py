"""Custom exception handlers for FastAPI."""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Resource not found"},
    )


async def unprocessable_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": str(exc)},
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception", exc_info=exc, path=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers."""
    app.add_exception_handler(404, not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(422, unprocessable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(500, internal_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, internal_error_handler)  # type: ignore[arg-type]
