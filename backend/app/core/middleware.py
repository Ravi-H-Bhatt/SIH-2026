"""
Rate Limiting & Security Middleware.

Prevents brute-force requests and enforces client request window limits.
"""

import time
from typing import Dict, Tuple
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Client IP tracker: ip -> (count, reset_time)
        self.clients: Dict[str, Tuple[int, float]] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Exempt health & docs endpoints
        if request.url.path in ["/api/v1/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        count, reset_time = self.clients.get(client_ip, (0, now + self.window_seconds))

        if now > reset_time:
            count = 0
            reset_time = now + self.window_seconds

        count += 1
        self.clients[client_ip] = (count, reset_time)

        if count > self.max_requests:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json"
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - count))
        return response
