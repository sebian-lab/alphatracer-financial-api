import time
from collections import defaultdict
from fastapi import Request, HTTPException, status

class InMemoryLimiter:
    def __init__(self, requests_limit: int, window_seconds: int):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        # Maps identifier (like IP address) to a list of request timestamps
        self.history = defaultdict(list)

    def check_rate_limit(self, key: str):
        now = time.time()
        # Remove timestamps outside the current window
        self.history[key] = [t for t in self.history[key] if now - t < self.window_seconds]
        
        if len(self.history[key]) >= self.requests_limit:
            wait_time = int(self.window_seconds - (now - self.history[key][0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Please try again in {wait_time} seconds.",
                headers={"Retry-After": str(wait_time)}
            )
        self.history[key].append(now)

# Auth endpoint limiter: max 5 requests per 60 seconds.
login_limiter = InMemoryLimiter(requests_limit=5, window_seconds=60)

def rate_limit_login(request: Request):
    """Dependency to limit requests per IP address."""
    ip = request.client.host if request.client else "unknown"
    login_limiter.check_rate_limit(ip)
