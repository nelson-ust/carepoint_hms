# carepoint_hms/app/middleware/rate_limit_middleware.py
from __future__ import annotations

"""
Rate limiting middleware for Carepoint HMS.

Purpose
-------
This middleware applies a simple in-memory rate limit per client and path.

What it does
------------
- identifies a client by IP address
- tracks request timestamps in memory
- enforces a rolling-window request limit
- returns HTTP 429 when the limit is exceeded
- exposes rate-limit headers on responses

Important note
--------------
This in-memory implementation is suitable for:
- local development
- single-process deployments
- early staging environments

For production across multiple app instances, replace this with Redis or
another shared store.
"""

from collections import defaultdict, deque
from threading import Lock
from time import time
from typing import Deque, Dict, Tuple

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.logger import get_request_logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    """

    def __init__(
        self,
        app,
        *,
        max_requests: int = 100,
        window_seconds: int = 60,
        by_path: bool = True,
        exclude_paths: tuple[str, ...] = ("/docs", "/openapi.json", "/redoc"),
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.by_path = by_path
        self.exclude_paths = exclude_paths

        # Store request timestamps per rate-limit key.
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Apply the rate limit and return a 429 response when exceeded.
        """
        request_id = getattr(request.state, "request_id", None)
        logger = get_request_logger(__name__, request_id=request_id)

        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        key = self._build_rate_limit_key(client_ip=client_ip, path=request.url.path)

        allowed, remaining, reset_in = self._check_rate_limit(key)

        if not allowed:
            logger.warning(
                "Rate limit exceeded.",
                extra={"request_id": request_id},
            )

            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": "Rate limit exceeded. Please try again later.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "detail": {
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                        "retry_after_seconds": reset_in,
                    },
                },
            )
            self._attach_rate_limit_headers(response, remaining=0, reset_in=reset_in)
            response.headers["Retry-After"] = str(reset_in)
            return response

        response = await call_next(request)
        self._attach_rate_limit_headers(response, remaining=remaining, reset_in=reset_in)
        return response

    def _is_excluded_path(self, path: str) -> bool:
        """
        Check whether a path should skip rate limiting.
        """
        return any(path.startswith(excluded) for excluded in self.exclude_paths)

    def _get_client_ip(self, request: Request) -> str:
        """
        Resolve client IP with support for common proxy headers.
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    def _build_rate_limit_key(self, *, client_ip: str, path: str) -> str:
        """
        Build a rate limit key.

        If by_path is enabled, each endpoint path gets its own rate-limit bucket.
        Otherwise the entire client shares one bucket.
        """
        return f"{client_ip}:{path}" if self.by_path else client_ip

    def _check_rate_limit(self, key: str) -> Tuple[bool, int, int]:
        """
        Apply a rolling-window rate limit check.

        Returns:
            tuple:
                allowed (bool),
                remaining_requests (int),
                reset_in_seconds (int)
        """
        now = time()
        window_start = now - self.window_seconds

        with self._lock:
            bucket = self._requests[key]

            # Remove timestamps that are outside the current window.
            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                oldest = bucket[0]
                reset_in = max(1, int((oldest + self.window_seconds) - now))
                return False, 0, reset_in

            bucket.append(now)
            remaining = max(0, self.max_requests - len(bucket))
            reset_in = self.window_seconds
            return True, remaining, reset_in

    def _attach_rate_limit_headers(self, response: Response, *, remaining: int, reset_in: int) -> None:
        """
        Add informative rate-limit headers to the response.
        """
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)