"""
API Sentinel - Asynchronous FastAPI / ASGI Middleware
Intercepts every HTTP request/response pair and immediately streams the response back.
Offloads runtime data capture and validation to background tasks using asyncio.create_task.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .capture import detect_auth_type, get_content_type, safe_parse_body, sanitize_headers
from .diff_engine import APIDiffEngine, OpenAPISpecParser
from .reporter import SentinelReporter
from .runtime_data import RuntimeData

logger = logging.getLogger("api_sentinel.middleware")


class APISentinelMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette ASGI middleware for real-time runtime data collection
    and contract drift detection.
    """

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

        self.exclude_paths: tuple[str, ...] = self._DEFAULT_EXCLUSIONS + tuple(
            exclude_paths or ()
        )

        # Parse spec at startup
        self._parser = OpenAPISpecParser.from_file(openapi_path)
        self._diff_engine = APIDiffEngine(self._parser)
        self._reporter = SentinelReporter()

        logger.info(
            "APISentinelMiddleware initialised | spec=%s | enabled=%s",
            openapi_path,
            enabled,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response, building RuntimeData and dispatching a background task.
        """
        if not self.enabled or self._is_excluded(request.url.path):
            return await call_next(request)

        # 1. Capture request body and metadata pre-execution
        try:
            request_body_bytes: bytes = await request.body()
        except Exception:
            logger.debug("APISentinelMiddleware: failed to buffer request body", exc_info=True)
            return await call_next(request)

        # Restore receive channel so downstream handlers can read body normally
        _cached_body = request_body_bytes

        async def _restore_receive() -> dict:
            return {"type": "http.request", "body": _cached_body, "more_body": False}

        request._receive = _restore_receive  # type: ignore[assignment]

        # Pre-capture request fields
        method = request.method
        endpoint = request.url.path
        query_parameters = dict(request.query_params)
        request_headers_raw = dict(request.headers)
        request_headers = sanitize_headers(request_headers_raw)
        
        # Detect auth type
        authentication_type = detect_auth_type(request_headers_raw, query_parameters)
        
        # Get content type
        request_content_type = get_content_type(request_headers_raw)
        request_body = safe_parse_body(_cached_body, request_content_type)

        # 2. Call upstream route handler
        response: Response = await call_next(request)

        # 3. Capture response body and metadata
        try:
            response_body_bytes = await self._buffer_response_body(response)
        except Exception:
            logger.debug("APISentinelMiddleware: failed to buffer response body", exc_info=True)
            return response

        # Post-capture response and routing fields
        path_parameters = dict(request.path_params)
        status_code = response.status_code
        response_headers_raw = dict(response.headers)
        response_headers = sanitize_headers(response_headers_raw)
        response_content_type = get_content_type(response_headers_raw)
        response_body = safe_parse_body(response_body_bytes, response_content_type)

        # Reconstruct response to send to client immediately
        headers = dict(response.headers)
        headers.pop("content-length", None)
        reconstructed = Response(
            content=response_body_bytes,
            status_code=status_code,
            headers=headers,
            media_type=response.media_type,
        )

        # 4. Construct RuntimeData
        runtime_data = RuntimeData(
            method=method,
            endpoint=endpoint,
            path_parameters=path_parameters,
            query_parameters=query_parameters,
            request_headers=request_headers,
            request_body=request_body,
            authentication_type=authentication_type,
            status_code=status_code,
            response_headers=response_headers,
            response_body=response_body,
        )

        # 5. Fire-and-forget background processing
        asyncio.create_task(
            self._process_captured_data(runtime_data),
            name=f"sentinel:capture:{method}:{endpoint}",
        )

        return reconstructed

    async def _process_captured_data(self, data: RuntimeData) -> None:
        """
        Background task to process the captured runtime data.
        """
        try:
            # Output structured capture information log
            logger.info(
                "Captured RuntimeData: method=%s, endpoint=%s, status_code=%d, auth=%s",
                data.method,
                data.endpoint,
                data.status_code,
                data.authentication_type,
            )

            # Keep backward compatibility with validation logic if configured
            if self._diff_engine:
                op_match = self._parser.get_operation(data.endpoint, data.method)
                matched_path = op_match[0] if op_match else None
                
                await self._diff_engine.analyze_payload_async(
                    method=data.method,
                    raw_path=data.endpoint,
                    matched_path=matched_path,
                    status_code=data.status_code,
                    query_params=data.query_parameters,
                    request_body=data.request_body,
                    response_body=data.response_body,
                    reporter=self._reporter,
                    print_clean=self.print_clean,
                )
        except Exception:
            logger.error("Error in Sentinel capture background task", exc_info=True)

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.exclude_paths)

    @staticmethod
    async def _buffer_response_body(response: Response) -> bytes:
        chunks: list[bytes] = []
        body_iterator = getattr(response, "body_iterator", None)

        if body_iterator is not None:
            async for chunk in body_iterator:
                if isinstance(chunk, str):
                    chunks.append(chunk.encode("utf-8"))
                else:
                    chunks.append(chunk)
        else:
            raw = getattr(response, "body", b"")
            chunks.append(raw if isinstance(raw, bytes) else raw.encode("utf-8"))

        return b"".join(chunks)
