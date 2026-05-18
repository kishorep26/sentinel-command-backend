import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"

        logger.info(
            "{method} {path} → {status} ({ms:.1f}ms) [{rid}]",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=duration_ms,
            rid=request_id,
        )
        return response
