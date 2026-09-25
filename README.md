# API Sentinel 🛡️

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenAPI 3.x](https://img.shields.io/badge/OpenAPI-3.x-green.svg)](https://swagger.io/specification/)

**API Sentinel** is an asynchronous FastAPI / ASGI middleware and developer telemetry dashboard that detects real-time contract drifts between runtime API payloads and your OpenAPI specification.

---

## 🚀 Key Features

- **⚡ Zero-Latency Async Interception**: Uses non-blocking background tasks (`asyncio.create_task`) and request buffering so your API responses stream immediately without waiting for validation.
- **🔍 Comprehensive Drift Detection**: Detects missing required fields, undocumented query/path parameters, type mismatches, undocumented HTTP status codes, and extra fields.
- **📊 Real-Time Developer Dashboard**: Built-in interactive dashboard with live polling, KPI metrics, pass/fail rate timeline charts, and severity breakdowns.
- **💾 Database Persistence**: Automatically records validation history and schema diffs to SQLite via SQLAlchemy (`aiosqlite`), persisting telemetry across server restarts.
- **🪄 OpenAPI Specification Wizard**: Visual form-based generator to design, preview, test, and save OpenAPI specs directly from the browser.
- **💻 CLI Tooling**: Built-in `api-sentinel` command-line interface to launch dashboards and validate specifications.

---

## 📦 Installation

### From PyPI (Standard):
```bash
pip install api-sentinel
```

### From GitHub (Latest):
```bash
pip install git+https://github.com/T41h4X/API_sentinel.git
```

---

## ⚡ Quick Start

### 1. Integrate Middleware with FastAPI

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
)

@app.get("/api/v1/users")
async def get_users():
    return [{"id": 1, "name": "Alice"}]
```

### 2. Launch the Sentinel Dashboard

Run the built-in dashboard from your terminal:

```bash
api-sentinel dashboard --port 8001
```

Open your browser at **[http://127.0.0.1:8001](http://127.0.0.1:8001)** to monitor incoming traffic, validation results, and contract drifts in real time.

---

## 💻 Command Line Interface (CLI)

API Sentinel provides the `api-sentinel` (or `sentinel`) CLI:

```bash
# Start the monitoring dashboard
api-sentinel dashboard --host 127.0.0.1 --port 8001

# Start dashboard in development mode with auto-reload
api-sentinel dashboard --reload

# Validate an OpenAPI specification file
api-sentinel validate --spec openapi.yaml

# Check installed version
api-sentinel version
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

Clone the repository and test the full demo application:

```bash
git clone https://github.com/T41h4X/API_sentinel.git
cd API_sentinel

# Create and activate environment
python -m venv .venv
.\.venv\Scripts\activate      # Windows
source .venv/bin/activate    # Linux / macOS

# Install in editable mode
pip install -e .

# Launch all demo services (Windows)
start_all.cmd
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
