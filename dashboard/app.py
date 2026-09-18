"""
API Sentinel - Interactive Dashboard Application
FastAPI web application for visualizing ValidationReport objects, endpoint statuses, schema diffs, and exporting reports.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
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
        async with AsyncSessionLocal() as session:
            record = ValidationReportRecord(
                endpoint=data["endpoint"],
                method=data["method"].upper(),
                status_code=data.get("status_code", 200),
                validation_status=data["validation_status"],
                severity=data.get("severity") if data.get("severity") != "NONE" else None,
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
