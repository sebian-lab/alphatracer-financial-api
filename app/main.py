"""
Main FastAPI application entry point.
Sets up routers, middleware, and startup events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create DB tables then pre-warm ticker cache."""
    from app.core.database import create_tables

    create_tables()

    # Pre-load both CSV sources into the DB so the first search request
    # doesn't block on a cold network fetch, and tickers like AAPL are
    # available immediately for transaction/watchlist lookups.
    try:
        from app.utils.csv_loader import load_tickers

        tickers = load_tickers()
        print(f"[startup] ticker cache ready — {len(tickers)} tickers loaded")
    except Exception as exc:
        print(f"[startup] ticker pre-warm failed (non-fatal): {exc}")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Alphatracer Backend",
        description=(
            "Portfolio tracking API with authentication, stock search (yfinance), "
            "buy/sell transactions, and watchlist management."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Load CORS allowed origins from settings
    origins = settings.allowed_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Industrial Observability: Jaeger Tracing & Loki Log Forwarding
    try:
        from app.core.telemetry import setup_telemetry
        from app.core.logging_loki import setup_loki_logging

        setup_telemetry(app)
        setup_loki_logging()
    except Exception as exc:
        print(f"[observability] Setup warning (non-fatal): {exc}")

    import time
    from collections import defaultdict
    from threading import Lock

    app_start_time = time.time()
    request_metrics = defaultdict(int)
    metrics_lock = Lock()

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        start_t = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_t

        # Dynamically record request count by method, route, and status
        path = request.url.path
        if path.startswith("/api/v1/stocks"):
            path = "/api/v1/stocks"
        elif path.startswith("/api/v1/portfolio"):
            path = "/api/v1/portfolio"
        with metrics_lock:
            request_metrics[(request.method, path, response.status_code)] += 1

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Process-Time"] = f"{duration:.4f}"
        return response

    # All routes mounted under /api/v1/...
    app.include_router(api_v1_router, prefix="/api")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        uptime = int(time.time() - app_start_time)
        lines = [
            "# HELP app_uptime_seconds Total seconds since application started",
            "# TYPE app_uptime_seconds counter",
            f"app_uptime_seconds {uptime}",
            "",
            "# HELP http_requests_total Total number of HTTP requests processed by endpoint and status",
            "# TYPE http_requests_total counter",
        ]
        with metrics_lock:
            if not request_metrics:
                lines.append('http_requests_total{method="GET",handler="/health",status="200"} 1')
            else:
                for (method, p, status), count in sorted(request_metrics.items()):
                    lines.append(f'http_requests_total{{method="{method}",handler="{p}",status="{status}"}} {count}')

        lines.extend([
            "",
            "# HELP app_status Application health status (1 = healthy)",
            "# TYPE app_status gauge",
            "app_status 1",
        ])
        return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/")
    def root():
        return {
            "message": "AlphaTracer DevSecOps API is running",
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics"
        }

    return app



app = create_app()
