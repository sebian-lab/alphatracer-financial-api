"""
Main FastAPI application entry point.
Sets up routers, middleware, and startup events.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
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

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # All routes mounted under /api/v1/...
    app.include_router(api_v1_router, prefix="/api")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
