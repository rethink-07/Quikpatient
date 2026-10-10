import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import router


class PrivacySafeFormatter(logging.Formatter):
    """Formats only explicitly supplied safe fields; never serializes request data."""

    def format(self, record: logging.LogRecord) -> str:
        message = getattr(record, "safe_event", "application_event")
        request_id = getattr(record, "request_id", "-")
        method = getattr(record, "http_method", "-")
        route = getattr(record, "route_template", "-")
        status = getattr(record, "status_code", "-")
        duration = getattr(record, "duration_ms", "-")
        return (
            f"{record.levelname} event={message} request_id={request_id} "
            f"method={method} route={route} status={status} duration_ms={duration}"
        )


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("quikpatient.api")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(PrivacySafeFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = _configure_logging()
app = FastAPI(
    title="QuikPatient API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.cors_origins.split(",") if origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def privacy_safe_request_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:64]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.error(
            "request_failed",
            extra={
                "safe_event": "request_failed",
                "request_id": request_id,
                "http_method": request.method,
                "route_template": getattr(request.scope.get("route"), "path", "unmatched"),
                "status_code": 500,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "internal_error", "message": "Request could not be completed."}},
        )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={
            "safe_event": "request_complete",
            "request_id": request_id,
            "http_method": request.method,
            "route_template": getattr(request.scope.get("route"), "path", "unmatched"),
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Do not return Pydantic's "input" values: validation errors may contain PHI.
    fields = sorted(
        ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path"))
        for error in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": "validation_error", "fields": fields}},
    )


app.include_router(router)
