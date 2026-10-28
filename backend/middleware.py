import logging
import re
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response


logger = logging.getLogger("fastapi.access")
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def setup_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlate_request(request: Request, call_next) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        context_token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        fields = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                "Unhandled exception while processing request",
                extra={**fields, "status_code": status_code},
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            logger.info(
                "HTTP request completed",
                extra={
                    **fields,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_context.reset(context_token)
