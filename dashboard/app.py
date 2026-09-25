"""
API Sentinel - Interactive Dashboard Application (Backward Compatibility Bridge)
Delegates to api_sentinel.dashboard.app for package namespacing.
"""

from api_sentinel.dashboard.app import (
    app,
    templates,
    fetch_aggregate_report,
    get_active_spec_path,
    validate_openapi_content,
    BASE_DIR,
    TEMPLATES_DIR,
    STATIC_DIR,
)

__all__ = [
    "app",
    "templates",
    "fetch_aggregate_report",
    "get_active_spec_path",
    "validate_openapi_content",
    "BASE_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
]
