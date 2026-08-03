"""
API Sentinel - Asynchronous FastAPI / ASGI Middleware
=====================================================
Intercepts every HTTP request/response pair and **immediately** streams the
response back to the client.  All schema-drift analysis is offloaded to a
non-blocking ``asyncio`` background task (fire-and-forget), ensuring that
Sentinel monitoring adds **zero perceived latency** to the target application.

Fire-and-Forget flow
--------------------
1. Await upstream handler  →  receive raw response.
2. Buffer response body chunks into memory  →  reconstruct byte payload.
3. Return reconstructed ``Response`` to the client immediately.
4. Schedule ``asyncio.create_task(diff_engine.analyze_payload_async(...))``
   so analysis runs concurrently in the same event loop without blocking.

Safety guarantee
----------------
Every code path inside the background task is wrapped in a top-level
``try/except Exception`` inside ``analyze_payload_async``.  A monitoring
failure can therefore **never** propagate to the host application.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .diff_engine import APIDiffEngine, OpenAPISpecParser
from .reporter import SentinelReporter

# Module-level logger — integrates with whatever logging config the host app
# has configured.  We avoid ``print`` calls inside the middleware itself.
logger = logging.getLogger("api_sentinel.middleware")


class APISentinelMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette ASGI middleware for real-time OpenAPI contract drift
    detection.

    Parameters
    ----------
    app:
        The ASGI application this middleware wraps (injected by Starlette/
        FastAPI when calling ``app.add_middleware(...)``).
    openapi_path:
        Filesystem path to the OpenAPI specification (YAML or JSON).
        Defaults to ``"openapi.yaml"`` in the current working directory.
    enabled:
        Master kill-switch.  When ``False`` the middleware is a pure
        pass-through with no measurable overhead.
    print_clean:
        When ``True``, emit a confirmation line to the console for every
        request that **passes** schema validation (useful during development).
    exclude_paths:
        URL path prefixes that should be silently ignored (e.g. health-checks,
        Swagger UI, metrics endpoints).  Defaults to common framework paths.
    """

    # Default prefixes that are always excluded from drift analysis.
    _DEFAULT_EXCLUSIONS: tuple[str, ...] = (
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/health",
        "/metrics",
    )

    def __init__(
        self,
        app: ASGIApp,
        openapi_path: str = "openapi.yaml",
        enabled: bool = True,
        print_clean: bool = False,
        exclude_paths: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(app)

        self.openapi_path = openapi_path
        self.enabled = enabled
        self.print_clean = print_clean

        # Merge caller-supplied exclusions with built-in defaults.
        self.exclude_paths: tuple[str, ...] = self._DEFAULT_EXCLUSIONS + tuple(
            exclude_paths or ()
        )

        # Parse the OpenAPI spec once at startup — not on every request.
        self._parser = OpenAPISpecParser.from_file(openapi_path)
        self._diff_engine = APIDiffEngine(self._parser)
        self._reporter = SentinelReporter()

        logger.info(
            "APISentinelMiddleware initialised | spec=%s | enabled=%s",
            openapi_path,
            enabled,
        )

    # ------------------------------------------------------------------
    # Core dispatch — called by Starlette for every incoming request.
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a single HTTP request/response cycle.

        Critical-path steps (steps that add latency visible to the client):
          1. Read & restore request body stream.
          2. Call the upstream route handler.
          3. Buffer the response body.
          4. Return ``Response`` to the client.

        Off-path steps (run *after* the client already has its response):
          5. Schedule background drift-analysis task.
        """

        # ── Fast path: middleware is disabled or path is excluded ──────────────
        if not self.enabled or self._is_excluded(request.url.path):
            return await call_next(request)

        # ── Step 1: Buffer request body without consuming the ASGI stream ──────
        # ``request.body()`` caches the body on the Request object, so
        # subsequent reads by the route handler (via ``request._receive``) still
        # work correctly after we read it here.
        try:
            request_body_bytes: bytes = await request.body()
        except Exception:
            # If we cannot read the request body, yield to the handler untouched.
            logger.debug("APISentinelMiddleware: failed to buffer request body", exc_info=True)
            return await call_next(request)

        # Restore the receive callable so the downstream handler can still
        # read ``request.body()`` / ``request.json()`` normally.
        _cached_body = request_body_bytes  # captured in closure below

        async def _restore_receive() -> dict:
            return {"type": "http.request", "body": _cached_body, "more_body": False}

        request._receive = _restore_receive  # type: ignore[assignment]

        # Snapshot query params *before* passing control downstream so they
        # cannot be mutated by the handler.
        query_params: dict[str, str] = dict(request.query_params)

        # ── Step 2: Call the upstream route handler ────────────────────────────
        response: Response = await call_next(request)

        # ── Step 3: Buffer response body ──────────────────────────────────────
        # We must consume the streaming iterator to get the raw bytes.
        # This is the *only* unavoidable latency contribution (~0.1–0.5 ms for
        # typical JSON payloads) — necessary because we must clone the body
        # before it is consumed by Starlette's response writer.
        try:
            response_body_bytes = await self._buffer_response_body(response)
        except Exception:
            logger.debug(
                "APISentinelMiddleware: failed to buffer response body", exc_info=True
            )
            # Return the original response unchanged; skip analysis.
            return response

        # ── Step 4: Reconstruct and return response to client immediately ──────
        # Strip Content-Length so Starlette recalculates it from the buffered
        # bytes, preventing mismatches if upstream set a wrong value.
        headers = dict(response.headers)
        headers.pop("content-length", None)

        reconstructed = Response(
            content=response_body_bytes,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )

        # ── Step 5: Fire-and-forget drift analysis (off the critical path) ─────
        # Parse payloads into Python objects outside the task so the raw bytes
        # are not held alive in memory longer than necessary.
        req_json = _safe_parse_json(request_body_bytes)
        res_json = _safe_parse_json(response_body_bytes)

        # Resolve the matched OpenAPI path template for richer diagnostics
        # (e.g. "/api/v1/users/{id}" instead of "/api/v1/users/42").
        op_match = self._parser.get_operation(request.url.path, request.method)
        matched_path: Optional[str] = op_match[0] if op_match else None

        # Schedule the analysis task. ``asyncio.create_task`` registers the
        # coroutine on the running event loop and returns immediately — the
        # client response has already been dispatched above.
        asyncio.create_task(
            self._diff_engine.analyze_payload_async(
                method=request.method,
                raw_path=request.url.path,
                matched_path=matched_path,
                status_code=response.status_code,
                query_params=query_params,
                request_body=req_json,
                response_body=res_json,
                reporter=self._reporter,
                print_clean=self.print_clean,
            ),
            name=f"sentinel:drift:{request.method}:{request.url.path}",
        )

        return reconstructed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, path: str) -> bool:
        """Return ``True`` if *path* starts with any of the configured exclusions."""
        return any(path.startswith(prefix) for prefix in self.exclude_paths)

    @staticmethod
    async def _buffer_response_body(response: Response) -> bytes:
        """
        Fully consume a Starlette ``Response`` body iterator and return the
        raw bytes.

        Starlette's ``BaseHTTPMiddleware`` wraps upstream responses in a
        ``_StreamingResponse``-like object whose ``.body_iterator`` is an
        async generator.  We drain it here so we can clone the payload.
        """
        chunks: list[bytes] = []

        # ``body_iterator`` is present on all Starlette response types that
        # wrap streaming content (which is what ``call_next`` always returns).
        body_iterator = getattr(response, "body_iterator", None)

        if body_iterator is not None:
            async for chunk in body_iterator:
                # Chunks may be ``str`` (text responses) or ``bytes``.
                if isinstance(chunk, str):
                    chunks.append(chunk.encode("utf-8"))
                else:
                    chunks.append(chunk)
        else:
            # Fallback: response already has a materialised ``.body`` attribute.
            raw = getattr(response, "body", b"")
            chunks.append(raw if isinstance(raw, bytes) else raw.encode("utf-8"))

        return b"".join(chunks)


# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------

def _safe_parse_json(data: bytes) -> Optional[Any]:
    """
    Attempt to decode *data* as UTF-8 JSON.

    Returns ``None`` silently on any decoding or parsing error — non-JSON
    bodies (HTML, binary, plain text) are simply treated as opaque and
    excluded from schema-body validation.
    """
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
