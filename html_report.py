"""
API Sentinel - HTML & JSON Report Generator (Backward Compatibility Bridge)
Delegates to api_sentinel.html_report for package namespacing.
"""

from api_sentinel.html_report import (
    generate_html_report,
    export_json_report,
    HTML_TEMPLATE_STRING,
)

__all__ = [
    "generate_html_report",
    "export_json_report",
    "HTML_TEMPLATE_STRING",
]
