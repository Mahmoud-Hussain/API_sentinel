# Database Implementation Details

This document explains the architectural changes made to transition the **API Sentinel** project from using volatile in-memory storage to a robust, persistent SQL database backend.

## 1. The Goal
Previously, API Sentinel stored intercepted API requests and schema validation drifts in a global memory variable (`_active_report`). This meant that every time the Dashboard server restarted, all historical validation logs were immediately lost. 

The goal was to implement a database-agnostic persistent storage system so that reports could survive server restarts, scale efficiently, and integrate data privacy features (PII masking) so it could safely be used by third-party companies.

## 2. Technologies Chosen
To achieve this, we introduced the following tools to the stack:
- **SQLAlchemy 2.0**: A powerful Database ORM that allows us to interact with the database using Python objects rather than writing raw SQL. This makes it completely database-agnostic (you can swap SQLite for PostgreSQL by just changing one string).
- **aiosqlite**: An asynchronous driver for SQLite. Since FastAPI is fully asynchronous, standard database calls would "block" the server and slow down real-time performance. This driver ensures that database inserts happen asynchronously in the background.
- **Pydantic-Settings**: For clean, environment-variable-based configuration (like defining database URLs and which fields should be masked).

## 3. How We Implemented It (Step-by-Step)

### A. Configuration & Privacy (`api_sentinel/config.py`)
We created a central settings file. This defines `DATABASE_URL` (defaulting to a local `sentinel.db` file) and sets up our **Data Privacy Rules**. For example, it defines a list of sensitive keys (`password`, `token`, `secret`) that must never be written to the database.

### B. The Database Layer (`api_sentinel/database/`)
- **`session.py`**: We created an `AsyncSessionLocal` object. This connects to the database asynchronously and creates the tables automatically if they don't exist.
- **`models.py`**: We defined two SQLAlchemy ORM models:
  1. `ValidationReportRecord`: Stores the top-level API request metadata (Endpoint, Method, Status Code, and the masked JSON request/response bodies).
  2. `DifferenceRecord`: A one-to-many relationship that stores the specific schema drifts (e.g., `MISSING_REQUIRED_FIELD`) linked to the report.

### C. Payload Masking (`api_sentinel/middleware.py`)
Before the middleware sends the captured payload to the dashboard, we implemented a recursive dictionary function called `_mask_payload`. It scans the entire JSON response/request. If it finds any key that matches our privacy list (like "password"), it replaces the actual data with the string `"***MASKED***"`. 

### D. The Dashboard Rewrite (`dashboard/app.py`)
The dashboard application was completely rewritten to query the database.
- The `fetch_aggregate_report()` function now runs an asynchronous SQL `SELECT` query to fetch the last 100 records from the database instead of returning a global memory object.
- The `/api/report/append` endpoint was updated to parse incoming data and use an `AsyncSession` to insert a new `ValidationReportRecord` and its associated `DifferenceRecord` items.
- **Type Safety Bugfix:** We encountered an issue where the diff engine outputted integer or list data types for `expected` values, which crashed the dashboard because the database expected strings. We added safe casting (`str(value)`) to ensure the dashboard never crashes when saving undocumented status codes (like `422`).

### E. PowerShell Compatibility Fixes (`HOW_TO_RUN.md`)
During testing, we discovered that Windows PowerShell aggressively strips double-quotes from `curl` commands, which was corrupting the JSON payload and causing standard FastAPI `422 Unprocessable Entity` errors rather than triggering the middleware's validation rules properly.
We updated the documentation to use native PowerShell `Invoke-RestMethod` commands to bypass this issue permanently.

## 4. The Result
- **Persistence:** Start and stop the servers all day long; your API drift logs will remain permanently saved in `sentinel.db`.
- **Privacy First:** Companies can safely route traffic through API Sentinel knowing passwords and tokens will never be stored on disk.
- **Ready to Scale:** Because it uses SQLAlchemy, a company could deploy API Sentinel to a cloud server, point `SENTINEL_DATABASE_URL` to a heavy-duty PostgreSQL cluster, and the application would scale without changing a single line of application code.
