"""
HTTPS enforcement and security-headers middleware.

This middleware does three things:

1. **HTTPS redirect** — if ``enforce_https`` is enabled and the inbound
   request is plain HTTP, return a 308 redirect to the HTTPS equivalent.
   Trusted proxies typically forward the original scheme through
   ``X-Forwarded-Proto``; we honour that header.

2. **HSTS** — when serving over HTTPS, attach a ``Strict-Transport-Security``
   header so browsers refuse to downgrade.

3. **Defensive headers** — attach ``X-Content-Type-Options``,
   ``X-Frame-Options``, ``Referrer-Policy`` and an opt-in
   ``Content-Security-Policy``.

Why CSP is *opt-in per path*
----------------------------
A strict ``default-src 'self'`` CSP breaks Swagger UI because the bundled
JS/CSS comes from ``cdn.jsdelivr.net``. The middleware therefore accepts
``csp_exempt_paths`` so callers can skip CSP for the developer-docs
endpoints (``/docs``, ``/redoc``, ``/openapi.json``) while keeping it on
everywhere else. The bundled default for the docs paths is shipped in
:data:`DEFAULT_CSP_EXEMPT_PATHS`.
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware


# Paths that should never be redirected to HTTPS (e.g., load-balancer
# health probes that intentionally hit HTTP). Override via constructor if
# desired.
DEFAULT_REDIRECT_EXEMPT_PATHS: frozenset[str] = frozenset(
    {"/health", "/health/db", "/ready"}
)


# Paths that should NOT receive a Content-Security-Policy header. The
# Swagger UI / ReDoc bundles fetch JS, CSS, and fonts from a CDN and
# evaluate inline scripts; a strict CSP turns the page blank even though
# the HTTP response is 200. We keep all the *other* defensive headers
# (X-Content-Type-Options, X-Frame-Options, etc.) for these paths.
DEFAULT_CSP_EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
        "/openapi.json",
    }
)


# A more permissive CSP that lets Swagger UI / ReDoc render correctly.
# Use this as the default when CSP is enabled globally (still narrower
# than disabling CSP entirely on the docs paths).
DEFAULT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enforce_https: bool = False,
        hsts_max_age: int = 60 * 60 * 24 * 365,
        include_subdomains: bool = True,
        preload: bool = False,
        csp: str | None = DEFAULT_CSP,
        redirect_exempt_paths: Iterable[str] = DEFAULT_REDIRECT_EXEMPT_PATHS,
        csp_exempt_paths: Iterable[str] = DEFAULT_CSP_EXEMPT_PATHS,
    ) -> None:
        super().__init__(app)
        self.enforce_https = enforce_https
        self.hsts_max_age = hsts_max_age
        self.include_subdomains = include_subdomains
        self.preload = preload
        self.csp = csp
        self.redirect_exempt_paths = frozenset(redirect_exempt_paths)
        self.csp_exempt_paths = frozenset(csp_exempt_paths)

    # ------------------------------------------------------------------

    def _request_scheme(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-proto")
        if forwarded:
            return forwarded.split(",")[0].strip().lower()
        return request.url.scheme.lower()

    def _hsts_value(self) -> str:
        parts = [f"max-age={int(self.hsts_max_age)}"]
        if self.include_subdomains:
            parts.append("includeSubDomains")
        if self.preload:
            parts.append("preload")
        return "; ".join(parts)

    def _is_csp_exempt(self, path: str) -> bool:
        if path in self.csp_exempt_paths:
            return True
        # Allow prefix match so e.g. ``/docs/oauth2-redirect`` is exempt
        # even if only ``/docs`` is registered.
        return any(path == p or path.startswith(p + "/") for p in self.csp_exempt_paths)

    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        scheme = self._request_scheme(request)

        if (
            self.enforce_https
            and scheme != "https"
            and path not in self.redirect_exempt_paths
        ):
            new_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(new_url), status_code=308)

        response = await call_next(request)

        # Always attach the safe defaults.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        # X-Frame-Options: DENY is fine for API responses but
        # SwaggerUI / ReDoc in iframes is uncommon. Keep the default.
        response.headers.setdefault("X-Frame-Options", "DENY")

        # CSP — apply only when configured AND the path isn't exempt.
        if self.csp and not self._is_csp_exempt(path):
            response.headers.setdefault("Content-Security-Policy", self.csp)

        # HSTS only when actually on HTTPS.
        if scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", self._hsts_value())

        return response
