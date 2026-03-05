"""
Rate limiting middleware using slowapi.
Protects student endpoints from abuse while allowing normal concurrency.

Usage:
    from middleware.rate_limit import limiter
    
    @router.post("/endpoint")
    @limiter.limit("3/minute")
    async def endpoint(request: Request, ...):
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from fastapi import FastAPI

# Single shared limiter instance — import this in route files
limiter = Limiter(key_func=get_remote_address)


def setup_rate_limiting(app: FastAPI):
    """Wire the shared limiter into the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
