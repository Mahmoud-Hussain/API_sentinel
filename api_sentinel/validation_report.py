"""
API Sentinel - Validation Report & Data Structures
Dataclasses and models representing validation reports, endpoint statuses, and schema drift summaries.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from api_sentinel.diff_engine import DriftIssue, DriftSeverity, DriftType


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


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


@dataclass
class ValidationReport:
    """ValidationReport aggregated summary object containing metrics and endpoint validation results."""
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
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        results = [EndpointValidationResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            title=data.get("title", "API Sentinel Schema Validation Report"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            results=results,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ValidationReport":
        data = json.loads(json_str)
        return cls.from_dict(data)
