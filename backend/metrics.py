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
AGRO_HTTP_REQUESTS = Counter(
    "agro_http_requests_total",
    "Total HTTP requests served by the AgroTech API demonstration.",
    labelnames=("method", "endpoint", "status_code"),
)
AGRO_HTTP_REQUEST_DURATION = Histogram(
    "agro_http_request_duration_seconds",
    "AgroTech API request duration in seconds.",
    labelnames=("method", "endpoint"),
)
AGRO_LAND_PORTFOLIO_QUERIES = Counter(
    "agro_land_portfolio_queries_total",
    "Demonstration land portfolio queries, counted from GET /items/.",
    labelnames=("outcome",),
)
AGRO_MA_LAND_QUERIES_ACTIVE = Gauge(
    "agro_ma_land_queries_active",
    "Active GET /items/ requests used as a demonstration M&A query signal.",
)
AGRO_EDGE_NODES = Gauge(
    "agro_edge_nodes",
    "Illustrative edge node counts; these are demo values, not live IoT telemetry.",
    labelnames=("region", "status"),
)
AGRO_EDGE_CPU_UTILIZATION = Gauge(
    "agro_edge_node_cpu_utilization_ratio",
    "Illustrative edge CPU utilization ratio; not collected from physical nodes.",
    labelnames=("region",),
)
AGRO_EDGE_MEMORY_UTILIZATION = Gauge(
    "agro_edge_node_memory_utilization_ratio",
    "Illustrative edge memory utilization ratio; not collected from physical nodes.",
    labelnames=("region",),
)

AGRO_LAND_PORTFOLIO_QUERIES.labels("success")
AGRO_LAND_PORTFOLIO_QUERIES.labels("error")
AGRO_EDGE_NODES.labels("sao_paulo", "online").set(2)
AGRO_EDGE_NODES.labels("mato_grosso", "online").set(1)
AGRO_EDGE_NODES.labels("mato_grosso", "offline").set(1)
AGRO_EDGE_CPU_UTILIZATION.labels("sao_paulo").set(0.63)
AGRO_EDGE_CPU_UTILIZATION.labels("mato_grosso").set(0.72)
AGRO_EDGE_MEMORY_UTILIZATION.labels("sao_paulo").set(0.55)
AGRO_EDGE_MEMORY_UTILIZATION.labels("mato_grosso").set(0.69)


def setup_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def record_http_metrics(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path.startswith("/metrics"):
            return await call_next(request)

        method = request.method
        path = request.url.path
        is_portfolio_query = method == "GET" and path in {"/items", "/items/"}
        status_code = "500"
        started_at = perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.labels(method).inc()
        if is_portfolio_query:
            AGRO_MA_LAND_QUERIES_ACTIVE.inc()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception as error:
            HTTP_EXCEPTIONS.labels(method, type(error).__name__).inc()
            raise
        finally:
            route = request.scope.get("route")
            endpoint = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(method, status_code).inc()
            HTTP_REQUEST_DURATION.labels(method).observe(perf_counter() - started_at)
            HTTP_REQUESTS_IN_PROGRESS.labels(method).dec()
            AGRO_HTTP_REQUESTS.labels(method, endpoint, status_code).inc()
            AGRO_HTTP_REQUEST_DURATION.labels(method, endpoint).observe(
                perf_counter() - started_at
            )
            if is_portfolio_query:
                outcome = "success" if status_code.startswith("2") else "error"
                AGRO_LAND_PORTFOLIO_QUERIES.labels(outcome).inc()
                AGRO_MA_LAND_QUERIES_ACTIVE.dec()

    app.mount("/metrics", make_asgi_app())
