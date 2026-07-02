"""
API v1 module — aggregates all router modules.
"""

from fastapi import APIRouter

from .auth      import router as auth_router
from .users     import router as users_router
from .stocks    import router as stocks_router
from .portfolio import router as portfolio_router
from .watchlist import router as watchlist_router
from .market    import router as market_router

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(stocks_router)
api_v1_router.include_router(portfolio_router)
api_v1_router.include_router(watchlist_router)
api_v1_router.include_router(market_router)

__all__ = ["api_v1_router"]
