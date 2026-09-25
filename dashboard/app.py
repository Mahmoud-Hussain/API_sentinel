"""
API Sentinel - Interactive Dashboard Application
FastAPI web application for visualizing ValidationReport objects, endpoint statuses, schema diffs, and exporting reports.
"""

import json
import os
import yaml
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api_sentinel.validation_report import (
    AggregateReport,
    EndpointValidationResult,
    ValidationStatus,
)
from api_sentinel.diff_engine import DriftSeverity, DriftType
from api_sentinel.openapi_parser import OpenAPIParser
from api_sentinel.openapi_generator import generate_openapi_yaml, generate_openapi_spec
from html_report import generate_html_report, export_json_report

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from api_sentinel.database.session import init_db, AsyncSessionLocal
from api_sentinel.database.models import ValidationReportRecord, DifferenceRecord
from api_sentinel.config import settings


# Root directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="API Sentinel Dashboard",
    description="Real-time OpenAPI schema drift & validation dashboard",
    version="0.1.0",
)

# Mount static files and templates
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
async def on_startup():
    await init_db()


async def fetch_aggregate_report() -> AggregateReport:
    """Fetches the latest reports from the database and constructs an AggregateReport."""
    report = AggregateReport(title="API Sentinel Schema Validation Report")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ValidationReportRecord)
            .options(selectinload(ValidationReportRecord.differences))
            .order_by(ValidationReportRecord.timestamp.desc())
            .limit(100)
        )
        records = result.scalars().all()
        
        for r in records:
            diffs = [{
                "issue_type": d.issue_type,
                "severity": d.severity,
                "location": d.location,
                "message": d.message,
                "expected": d.expected,
                "actual": d.actual
            } for d in r.differences]
            
            report.results.append(EndpointValidationResult(
                endpoint=r.endpoint,
                method=r.method,
                status_code=r.status_code,
                validation_status=ValidationStatus(r.validation_status),
                severity=DriftSeverity(r.severity) if r.severity else None,
                timestamp=r.timestamp.isoformat() if r.timestamp else datetime.now(timezone.utc).isoformat(),
                expected_schema=r.expected_schema,
                actual_schema=r.actual_schema,
                differences=diffs
            ))
            
    return report


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Renders the dashboard home page with summary metrics and endpoint table."""
    report = await fetch_aggregate_report()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"report": report},
    )


@app.get("/endpoint/detail", response_class=HTMLResponse)
async def endpoint_detail(request: Request, index: int = 0):
    """Renders the detailed view for a single endpoint schema validation result."""
    report = await fetch_aggregate_report()
    results = report.results

    if 0 <= index < len(results):
        res = results[index]
    else:
        res = EndpointValidationResult(
            endpoint="/api/unknown",
            method="GET",
            status_code=404,
            validation_status=ValidationStatus.FAILED,
            severity=DriftSeverity.ERROR,
        )

    expected_json = json.dumps(res.expected_schema or {}, indent=2)
    actual_json = json.dumps(res.actual_schema or {}, indent=2)

    return templates.TemplateResponse(
        request=request,
        name="endpoint_detail.html",
        context={
            "res": res,
            "expected_schema_json": expected_json,
            "actual_schema_json": actual_json,
        },
    )


@app.get("/api/report")
async def get_report_json():
    """Returns the active ValidationReport as JSON."""
    report = await fetch_aggregate_report()
    return JSONResponse(content=report.to_dict())


@app.post("/api/report/append")
async def append_report_result(data: dict):
    """Appends an individual EndpointValidationResult to the database."""
    if settings.selective_persistence:
        if data.get("validation_status") == ValidationStatus.PASSED.value:
            return {"status": "skipped", "reason": "selective persistence enabled, ignored PASSED"}

    try:
        ts = None
        if data.get("timestamp"):
            try:
                ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            record = ValidationReportRecord(
                endpoint=data["endpoint"],
                method=data["method"].upper(),
                status_code=data.get("status_code", 200),
                validation_status=data["validation_status"],
                severity=data.get("severity") if data.get("severity") != "NONE" else None,
                timestamp=ts,
                expected_schema=data.get("expected_schema"),
                actual_schema=data.get("actual_schema"),
            )
            for diff in data.get("differences", []):
                record.differences.append(DifferenceRecord(
                    issue_type=diff.get("issue_type"),
                    severity=diff.get("severity"),
                    location=diff.get("location"),
                    message=diff.get("message"),
                    expected=str(diff.get("expected")) if diff.get("expected") is not None else None,
                    actual=str(diff.get("actual")) if diff.get("actual") is not None else None
                ))
            
            session.add(record)
            
            # Retention policy cleanup
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
            await session.execute(delete(ValidationReportRecord).where(ValidationReportRecord.timestamp < cutoff_date))
            
            await session.commit()

        return {"status": "success"}
    except Exception as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


@app.post("/api/report/clear")
async def clear_report():
    """Clears all validation results from the database."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(ValidationReportRecord))
            await session.commit()
        return {"status": "cleared", "total_endpoints": 0}
    except Exception as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


@app.get("/api/export/json")
async def export_json():
    """Downloads the current ValidationReport as a formatted JSON file."""
    report = await fetch_aggregate_report()
    json_str = report.to_json()
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="validation_report.json"'},
    )


@app.get("/api/export/html")
async def export_html():
    """Downloads the current ValidationReport as a standalone HTML file."""
    report = await fetch_aggregate_report()
    html_str = generate_html_report(report)
    return Response(
        content=html_str,
        media_type="text/html",
        headers={"Content-Disposition": 'attachment; filename="validation_report.html"'},
    )


# ===========================================================================
# OpenAPI Documentation Management Helpers & Endpoints
# ===========================================================================

def get_active_spec_path() -> str:
    """Returns the absolute path to the active OpenAPI specification file."""
    path = getattr(settings, "openapi_spec_path", "openapi.yaml")
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def validate_openapi_content(content_str: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates an OpenAPI YAML or JSON specification string.
    Reuses the existing OpenAPIParser without duplicate validation engines.

    Returns
    -------
    tuple[bool, dict | None, str | None]
        (is_valid, summary_dict, error_message)
    """
    if not content_str or not content_str.strip():
        return False, None, "OpenAPI specification content cannot be empty."

    # Parse YAML or JSON (yaml.safe_load parses both YAML and JSON)
    try:
        data = yaml.safe_load(content_str)
    except Exception as exc:
        return False, None, f"Invalid YAML/JSON syntax: {str(exc)}"

    if not isinstance(data, dict):
        return False, None, "OpenAPI specification must be a valid JSON/YAML object/dictionary."

    # Validate version field (OpenAPI 3.x or Swagger 2.0)
    version_str = data.get("openapi") or data.get("swagger")
    if not version_str:
        return False, None, "Missing required OpenAPI version field ('openapi' or 'swagger')."

    # Validate info object
    info = data.get("info")
    if not isinstance(info, dict):
        return False, None, "Missing or invalid 'info' section in OpenAPI specification."

    title = str(info.get("title", "Untitled API"))
    api_version = str(info.get("version", "1.0.0"))

    # Validate paths object
    paths = data.get("paths")
    if not isinstance(paths, dict):
        return False, None, "Missing or invalid 'paths' section in OpenAPI specification."

    # Reuse OpenAPIParser to parse routes, parameters, and schema structures
    try:
        parser = OpenAPIParser.from_dict(data)
        
        endpoints_summary: List[Dict[str, Any]] = []
        for path_template, path_item in parser.paths.items():
            if isinstance(path_item, dict):
                methods = [
                    m.upper()
                    for m in path_item.keys()
                    if m.lower() in {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
                ]
                endpoints_summary.append({
                    "path": path_template,
                    "methods": methods,
                    "summary": path_item.get("summary", ""),
                })

        summary = {
            "title": title,
            "version": api_version,
            "openapi_version": str(version_str),
            "description": info.get("description", ""),
            "paths_count": len(paths),
            "endpoints": endpoints_summary,
            "schemas_count": len(parser.components_schemas),
        }
        return True, summary, None
    except Exception as exc:
        return False, None, f"OpenAPI schema structure error: {str(exc)}"


@app.get("/openapi-docs", response_class=HTMLResponse)
async def openapi_docs_page(request: Request):
    """Renders the OpenAPI Documentation & Specification Management page."""
    spec_path = get_active_spec_path()
    content = ""
    if os.path.exists(spec_path):
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            content = f"# Error reading active specification: {exc}"

    is_valid, summary, error = validate_openapi_content(content)

    return templates.TemplateResponse(
        request=request,
        name="openapi_docs.html",
        context={
            "spec_content": content,
            "spec_path": getattr(settings, "openapi_spec_path", "openapi.yaml"),
            "is_valid": is_valid,
            "summary": summary,
            "error": error,
        },
    )


@app.get("/api/openapi/current")
async def get_current_openapi_spec():
    """Returns the active OpenAPI specification content and parsed summary."""
    spec_path = get_active_spec_path()
    if not os.path.exists(spec_path):
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"Specification file not found at {spec_path}"},
        )

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to read file: {str(exc)}"},
        )

    is_valid, summary, error = validate_openapi_content(content)
    fmt = "json" if spec_path.endswith(".json") else "yaml"

    return {
        "content": content,
        "format": fmt,
        "path": getattr(settings, "openapi_spec_path", "openapi.yaml"),
        "valid": is_valid,
        "summary": summary,
        "error": error,
    }


@app.post("/api/openapi/generate")
async def generate_openapi_from_form(payload: Dict[str, Any]):
    """
    Generates a standard OpenAPI 3.0.3 YAML document from structured form inputs
    and validates it using the existing validate_openapi_content function.
    """
    try:
        yaml_content = generate_openapi_yaml(payload)
        is_valid, summary, error = validate_openapi_content(yaml_content)
        return {
            "status": "success" if is_valid else "invalid",
            "yaml": yaml_content,
            "valid": is_valid,
            "summary": summary,
            "error": error,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "valid": False,
                "message": f"Failed to generate OpenAPI specification: {str(exc)}",
                "error": str(exc),
            },
        )


@app.post("/api/openapi/validate")
async def validate_openapi_spec(payload: Dict[str, Any]):
    """Validates an OpenAPI specification document without saving."""
    content = payload.get("content", "")
    is_valid, summary, error = validate_openapi_content(content)
    return {
        "valid": is_valid,
        "summary": summary,
        "error": error,
    }


@app.post("/api/openapi/save")
async def save_active_openapi_spec(payload: Dict[str, Any]):
    """Validates and persists the active OpenAPI specification file."""
    content = payload.get("content", "")
    is_valid, summary, error = validate_openapi_content(content)

    if not is_valid:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": f"Cannot save invalid OpenAPI specification: {error}",
                "error": error,
            },
        )

    spec_path = get_active_spec_path()
    try:
        # Write validated content to active specification file
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "saved",
            "path": getattr(settings, "openapi_spec_path", "openapi.yaml"),
            "message": "Active OpenAPI specification successfully updated and persisted.",
            "summary": summary,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to save specification file: {str(exc)}"},
        )

