"""
API Sentinel - Validation Report & Data Structures
Defines two report models:
  - ValidationReport: single request/response cycle result (used by ContractValidator)
  - AggregateReport:  aggregated summary over many endpoints (used by dashboard/html_report)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from api_sentinel.diff_engine import DriftIssue, DriftSeverity, DriftType


# ===========================================================================
# Enums
# ===========================================================================


class ValidationStatus(str, Enum):
    """Overall validation outcome."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class ValidationSeverity(str, Enum):
    """Severity level for individual validation differences."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class DifferenceType(str, Enum):
    """Classification of schema differences detected during validation."""
    MISSING_FIELD = "MISSING_FIELD"
    EXTRA_FIELD = "EXTRA_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    ENUM_VIOLATION = "ENUM_VIOLATION"
    REQUIRED_FIELD_VIOLATION = "REQUIRED_FIELD_VIOLATION"
    NULLABLE_VIOLATION = "NULLABLE_VIOLATION"
    FORMAT_MISMATCH = "FORMAT_MISMATCH"
    UNDOCUMENTED_ENDPOINT = "UNDOCUMENTED_ENDPOINT"
    UNDOCUMENTED_STATUS_CODE = "UNDOCUMENTED_STATUS_CODE"
    UNDOCUMENTED_QUERY_PARAM = "UNDOCUMENTED_QUERY_PARAM"
    MISSING_REQUIRED_QUERY_PARAM = "MISSING_REQUIRED_QUERY_PARAM"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"
    PATH_PARAM_TYPE_MISMATCH = "PATH_PARAM_TYPE_MISMATCH"


# ===========================================================================
# Difference dataclass
# ===========================================================================


@dataclass
class Difference:
    """
    A single schema difference found during validation.

    Attributes
    ----------
    diff_type : DifferenceType
        The classification of this difference.
    severity : ValidationSeverity
        How critical this difference is.
    location : str
        Where in the request/response the difference was found.
        Examples: 'request_body', 'response_body', 'query_params',
                  'path_params', 'status_code', 'content_type'
    json_path : str
        JSON path to the specific field (e.g., '$.user.name', '$.items[0].id').
    message : str
        Human-readable description of the difference.
    expected : Any
        What the OpenAPI spec defines.
    actual : Any
        What was observed at runtime.
    """
    diff_type: DifferenceType
    severity: ValidationSeverity
    location: str
    json_path: str
    message: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "diff_type": self.diff_type.value,
            "severity": self.severity.value,
            "location": self.location,
            "json_path": self.json_path,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


# ===========================================================================
# ValidationReport — single request/response cycle result
# (used by ContractValidator._build_report and test_validation_report.py)
# ===========================================================================


@dataclass
class ValidationReport:
    """
    Complete validation report for a single runtime request/response cycle.

    Attributes
    ----------
    endpoint : str
        The matched OpenAPI path template (e.g., '/api/v1/users/{id}').
    method : str
        HTTP method (GET, POST, PUT, DELETE, PATCH, etc.).
    status : ValidationStatus
        Overall validation outcome (PASSED, FAILED, WARNING).
    severity : ValidationSeverity
        Highest severity among all differences found.
    status_code : int
        The HTTP response status code observed at runtime.
    expected_schema : dict
        The expected schema from the OpenAPI specification.
    actual_schema : dict
        The inferred schema from the runtime payload.
    differences : List[Difference]
        All schema differences detected.
    timestamp : str
        ISO 8601 timestamp of when validation was performed.
    """
    endpoint: str
    method: str
    status: ValidationStatus
    severity: ValidationSeverity
    status_code: int
    expected_schema: Dict[str, Any] = field(default_factory=dict)
    actual_schema: Dict[str, Any] = field(default_factory=dict)
    differences: List[Difference] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_valid(self) -> bool:
        """Returns True if no ERROR-level differences were found."""
        return not any(
            d.severity == ValidationSeverity.ERROR for d in self.differences
        )

    @property
    def error_count(self) -> int:
        """Number of ERROR-level differences."""
        return sum(1 for d in self.differences if d.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Number of WARNING-level differences."""
        return sum(1 for d in self.differences if d.severity == ValidationSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Number of INFO-level differences."""
        return sum(1 for d in self.differences if d.severity == ValidationSeverity.INFO)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full report to a plain dictionary."""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "status": self.status.value,
            "severity": self.severity.value,
            "status_code": self.status_code,
            "expected_schema": self.expected_schema,
            "actual_schema": self.actual_schema,
            "differences": [d.to_dict() for d in self.differences],
            "timestamp": self.timestamp,
        }

    def summary(self) -> str:
        """One-line human-readable summary."""
        return (
            f"[{self.status.value}] {self.method} {self.endpoint} "
            f"({self.status_code}) — "
            f"{self.error_count} errors, {self.warning_count} warnings, "
            f"{self.info_count} info"
        )

    @classmethod
    def create_passed(
        cls,
        endpoint: str,
        method: str,
        status_code: int,
        expected_schema: Optional[Dict[str, Any]] = None,
        actual_schema: Optional[Dict[str, Any]] = None,
    ) -> "ValidationReport":
        """Factory for a clean validation with no differences."""
        return cls(
            endpoint=endpoint,
            method=method,
            status=ValidationStatus.PASSED,
            severity=ValidationSeverity.INFO,
            status_code=status_code,
            expected_schema=expected_schema or {},
            actual_schema=actual_schema or {},
            differences=[],
        )


# ===========================================================================
# EndpointValidationResult — per-endpoint result for aggregate reports
# (used by AggregateReport and test_dashboard_reporting.py)
# ===========================================================================


@dataclass
class EndpointValidationResult:
    """Represents the validation result for a single endpoint execution or spec endpoint."""
    endpoint: str
    method: str
    status_code: int
    validation_status: ValidationStatus
    severity: Optional[DriftSeverity] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expected_schema: Optional[Dict[str, Any]] = None
    actual_schema: Optional[Dict[str, Any]] = None
    differences: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method.upper(),
            "status_code": self.status_code,
            "validation_status": self.validation_status.value if isinstance(self.validation_status, Enum) else str(self.validation_status),
            "severity": self.severity.value if isinstance(self.severity, Enum) and self.severity else (str(self.severity) if self.severity else "NONE"),
            "timestamp": self.timestamp,
            "expected_schema": self.expected_schema,
            "actual_schema": self.actual_schema,
            "differences": self.differences,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EndpointValidationResult":
        val_status = ValidationStatus(data["validation_status"]) if isinstance(data.get("validation_status"), str) else data["validation_status"]
        sev = DriftSeverity(data["severity"]) if data.get("severity") and data["severity"] != "NONE" else None
        return cls(
            endpoint=data["endpoint"],
            method=data["method"],
            status_code=data.get("status_code", 200),
            validation_status=val_status,
            severity=sev,
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            expected_schema=data.get("expected_schema"),
            actual_schema=data.get("actual_schema"),
            differences=data.get("differences", []),
        )


# ===========================================================================
# AggregateReport — aggregated summary object used by dashboard/html reporting
# (previously the second ValidationReport class — renamed to avoid collision)
# ===========================================================================


@dataclass
class AggregateReport:
    """AggregateReport summary object containing metrics and endpoint validation results."""
    title: str = "API Sentinel Schema Validation Report"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    results: List[EndpointValidationResult] = field(default_factory=list)

    @property
    def total_endpoints(self) -> int:
        return len(self.results)

    @property
    def passed_endpoints(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.PASSED)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.WARNING)

    @property
    def failed_endpoints(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.FAILED)

    def add_result(self, result: EndpointValidationResult) -> None:
        self.results.append(result)

    @property
    def timeline(self) -> Dict[str, Any]:
        """Calculates a 12-bar validation pass/fail timeline from the recorded results."""
        return self.compute_timeline(num_bars=12)

    def compute_timeline(self, num_bars: int = 12) -> Dict[str, Any]:
        """
        Computes timeline buckets for the Pass/Fail Rate chart.
        Returns a dictionary with 'bars', 'start_label', 'mid_label', and 'end_label'.
        """
        if not self.results:
            bars = [
                {
                    "height_pct": 6,
                    "status": "EMPTY",
                    "pass_rate": 0,
                    "total": 0,
                    "passed": 0,
                    "warning": 0,
                    "failed": 0,
                    "label": "—",
                    "tooltip": "No validation telemetry recorded yet",
                    "timestamp_label": "",
                }
                for _ in range(num_bars)
            ]
            return {
                "bars": bars,
                "start_label": "-24h",
                "mid_label": "-12h",
                "end_label": "Now",
            }

        # self.results are stored newest-first. Reverse to chronological order (oldest first).
        results_asc = list(reversed(self.results))
        total_items = len(results_asc)

        def _fmt_ts(iso_str: str) -> str:
            if not iso_str:
                return ""
            try:
                dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                return dt.strftime("%H:%M:%S")
            except Exception:
                return str(iso_str)[11:19] if len(str(iso_str)) >= 19 else str(iso_str)

        start_label = _fmt_ts(results_asc[0].timestamp) or "-24h"
        mid_label = _fmt_ts(results_asc[len(results_asc) // 2].timestamp) or "-12h"
        end_label = "Now"

        bars = []
        if total_items <= num_bars:
            # Map each item directly to an individual bar slot
            for r in results_asc:
                status_str = r.validation_status.value if isinstance(r.validation_status, Enum) else str(r.validation_status)
                status_str = status_str.upper()
                ts_str = _fmt_ts(r.timestamp)

                if status_str == "PASSED":
                    bars.append({
                        "height_pct": 100,
                        "status": "PASSED",
                        "pass_rate": 100,
                        "total": 1,
                        "passed": 1,
                        "warning": 0,
                        "failed": 0,
                        "label": "100%",
                        "tooltip": f"{r.method} {r.endpoint} • PASSED ({r.status_code})",
                        "timestamp_label": ts_str,
                    })
                elif status_str == "WARNING":
                    bars.append({
                        "height_pct": 70,
                        "status": "WARNING",
                        "pass_rate": 70,
                        "total": 1,
                        "passed": 0,
                        "warning": 1,
                        "failed": 0,
                        "label": "Warn",
                        "tooltip": f"{r.method} {r.endpoint} • WARNING ({r.status_code})",
                        "timestamp_label": ts_str,
                    })
                else:
                    bars.append({
                        "height_pct": 40,
                        "status": "FAILED",
                        "pass_rate": 30,
                        "total": 1,
                        "passed": 0,
                        "warning": 0,
                        "failed": 1,
                        "label": "Fail",
                        "tooltip": f"{r.method} {r.endpoint} • FAILED ({r.status_code})",
                        "timestamp_label": ts_str,
                    })

            # Fill remaining slots with EMPTY bars
            for _ in range(num_bars - total_items):
                bars.append({
                    "height_pct": 6,
                    "status": "EMPTY",
                    "pass_rate": 0,
                    "total": 0,
                    "passed": 0,
                    "warning": 0,
                    "failed": 0,
                    "label": "—",
                    "tooltip": "Awaiting validation telemetry...",
                    "timestamp_label": "",
                })
        else:
            # Partition chronological results into num_bars buckets
            for i in range(num_bars):
                start_idx = (i * total_items) // num_bars
                end_idx = ((i + 1) * total_items) // num_bars
                bucket = results_asc[start_idx:end_idx]

                if not bucket:
                    bars.append({
                        "height_pct": 6,
                        "status": "EMPTY",
                        "pass_rate": 0,
                        "total": 0,
                        "passed": 0,
                        "warning": 0,
                        "failed": 0,
                        "label": "—",
                        "tooltip": "No validation data in this interval",
                        "timestamp_label": "",
                    })
                    continue

                b_total = len(bucket)
                b_passed = sum(1 for x in bucket if (x.validation_status.value if isinstance(x.validation_status, Enum) else str(x.validation_status)).upper() == "PASSED")
                b_warn = sum(1 for x in bucket if (x.validation_status.value if isinstance(x.validation_status, Enum) else str(x.validation_status)).upper() == "WARNING")
                b_failed = sum(1 for x in bucket if (x.validation_status.value if isinstance(x.validation_status, Enum) else str(x.validation_status)).upper() == "FAILED")
                pass_rate = round((b_passed / b_total) * 100) if b_total > 0 else 0

                b_start_ts = _fmt_ts(bucket[0].timestamp)
                b_end_ts = _fmt_ts(bucket[-1].timestamp)
                time_range_str = f"{b_start_ts} - {b_end_ts}" if b_start_ts != b_end_ts else b_start_ts

                if b_failed > 0:
                    status = "FAILED"
                    height = max(pass_rate, 25)
                    label = f"{pass_rate}%"
                    tooltip = f"Pass Rate: {pass_rate}% ({b_passed}/{b_total} passed, {b_failed} failed) • {time_range_str}"
                elif b_warn > 0:
                    status = "WARNING"
                    height = max(pass_rate, 50)
                    label = f"{pass_rate}%"
                    tooltip = f"Pass Rate: {pass_rate}% ({b_passed}/{b_total} passed, {b_warn} warnings) • {time_range_str}"
                else:
                    status = "PASSED"
                    height = 100
                    label = "100%"
                    tooltip = f"100% Passed ({b_passed}/{b_total} passed) • {time_range_str}"

                bars.append({
                    "height_pct": height,
                    "status": status,
                    "pass_rate": pass_rate,
                    "total": b_total,
                    "passed": b_passed,
                    "warning": b_warn,
                    "failed": b_failed,
                    "label": label,
                    "tooltip": tooltip,
                    "timestamp_label": time_range_str,
                })

        return {
            "bars": bars,
            "start_label": start_label,
            "mid_label": mid_label,
            "end_label": end_label,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "timestamp": self.timestamp,
            "summary": {
                "total_endpoints": self.total_endpoints,
                "passed_endpoints": self.passed_endpoints,
                "warning_count": self.warning_count,
                "failed_endpoints": self.failed_endpoints,
            },
            "timeline": self.timeline,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregateReport":
        results = [EndpointValidationResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            title=data.get("title", "API Sentinel Schema Validation Report"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            results=results,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AggregateReport":
        data = json.loads(json_str)
        return cls.from_dict(data)
