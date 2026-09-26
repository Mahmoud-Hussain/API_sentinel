# API Sentinel 🛡️

[![PyPI version](https://img.shields.io/pypi/v/api-drift-detector.svg)](https://pypi.org/project/api-drift-detector/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenAPI 3.x](https://img.shields.io/badge/OpenAPI-3.x-green.svg)](https://swagger.io/specification/)

**API Sentinel** (`api-drift-detector`) is an asynchronous FastAPI / ASGI middleware and developer telemetry dashboard that detects real-time contract drifts between runtime API payloads and your OpenAPI specification.

---

## 🚀 Key Features

- **⚡ Zero-Latency Async Interception**: Uses non-blocking background tasks (`asyncio.create_task`) and request buffering so your API responses stream immediately without waiting for validation.
- **🔍 Comprehensive Drift Detection**: Detects missing required fields, undocumented query/path parameters, type mismatches, undocumented HTTP status codes, and extra fields.
- **📊 Real-Time Developer Dashboard**: Built-in interactive dashboard with live polling, KPI metrics, pass/fail rate timeline charts, and severity breakdowns.
- **💾 Database Persistence**: Automatically records validation history and schema diffs to SQLite via SQLAlchemy (`aiosqlite`), persisting telemetry across server restarts.
- **🪄 OpenAPI Specification Wizard**: Visual form-based generator to design, preview, test, and save OpenAPI specs directly from the browser.
- **💻 CLI Tooling**: Built-in `api-drift-detector` (and `api-sentinel`) command-line interface to launch dashboards and validate specifications.

---

## 📦 Installation

### From PyPI (Recommended):
```bash
pip install api-drift-detector
```

### From GitHub (Latest source):
```bash
pip install git+https://github.com/T41h4X/API_sentinel.git
```

---

## ⚡ Quick Start

### 1. Launch the Sentinel Dashboard (Terminal 1)

Start the monitoring dashboard on port `8001`:

```bash
api-drift-detector dashboard
```
*(or use `api-sentinel dashboard`)*

Open your browser at **[http://127.0.0.1:8001](http://127.0.0.1:8001)** to monitor incoming traffic, validation results, and contract drifts in real time.

---

### 2. Integrate Middleware in Your FastAPI App (Terminal 2)

Add `APISentinelMiddleware` to your FastAPI application:

```python
from fastapi import FastAPI
from api_sentinel import APISentinelMiddleware

app = FastAPI(title="My API")

# Register Sentinel Middleware
app.add_middleware(
    APISentinelMiddleware,
    openapi_path="openapi.yaml",            # Path to your OpenAPI spec
    dashboard_url="http://127.0.0.1:8001",  # URL of the Sentinel dashboard
    enabled=True,
    print_clean=True,
)

@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int):
    # Any schema mismatch or extra undocumented fields will trigger live alerts!
    return {"id": user_id, "name": "Alice"}
```

Run your FastAPI server on port `8000`:
```bash
uvicorn app:app --reload --port 8000
```

Any request sent to your FastAPI server (`http://127.0.0.1:8000/api/v1/users/1`) is intercepted, checked against `openapi.yaml`, and streamed directly into your dashboard!

---

## 💻 Command Line Interface (CLI)

The package provides the `api-drift-detector` (and `api-sentinel`) CLI:

```bash
# Start the monitoring dashboard (default: http://127.0.0.1:8001)
api-drift-detector dashboard

# Start on custom host or port
api-drift-detector dashboard --host 0.0.0.0 --port 8080

# Start dashboard in development mode with auto-reload
api-drift-detector dashboard --reload

# Validate an OpenAPI specification file in CI/CD pipelines
api-drift-detector validate --spec openapi.yaml

# Check installed version
api-drift-detector version
```

---

## ⚙️ Configuration

API Sentinel can be configured using environment variables (prefixed with `SENTINEL_`) or a `.env` file:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SENTINEL_DATABASE_URL` | `sqlite+aiosqlite:///./sentinel.db` | SQLAlchemy database connection string |
| `SENTINEL_RETENTION_DAYS` | `30` | Number of days to retain validation records before cleanup |
| `SENTINEL_MASKED_FIELDS` | `["password", "token", "credit_card", "authorization"]` | Sensitive payload fields automatically masked |
| `SENTINEL_SELECTIVE_PERSISTENCE` | `false` | When `true`, only saves `WARNING` and `FAILED` validation results |
| `SENTINEL_OPENAPI_SPEC_PATH` | `openapi.yaml` | Default OpenAPI specification file path |

---

## 🧪 Running the Demo Locally

Clone the repository and test the full demo application with sample drifts:

```bash
git clone https://github.com/T41h4X/API_sentinel.git
cd API_sentinel

# Create and activate environment
python -m venv .venv
.\.venv\Scripts\activate      # Windows
source .venv/bin/activate    # Linux / macOS

# Install package
pip install -e .

# Launch all demo services (Windows)
start_all.cmd
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
