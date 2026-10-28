from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.requests import Request
from starlette.responses import Response


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total number of HTTP requests.",
    labelnames=("method", "status_code"),
)
HTTP_EXCEPTIONS = Counter(
    "http_exceptions_total",
    "Total number of uncaught HTTP request exceptions.",
    labelnames=("method", "exception"),
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method",),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
    labelnames=("method",),
)


def setup_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def record_http_metrics(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/metrics"):
            return await call_next(request)

        method = request.method
        status_code = "500"
        started_at = perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.labels(method).inc()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception as error:
            HTTP_EXCEPTIONS.labels(method, type(error).__name__).inc()
            raise
        finally:
            HTTP_REQUESTS.labels(method, status_code).inc()
            HTTP_REQUEST_DURATION.labels(method).observe(perf_counter() - started_at)
            HTTP_REQUESTS_IN_PROGRESS.labels(method).dec()

    app.mount("/metrics", make_asgi_app())
