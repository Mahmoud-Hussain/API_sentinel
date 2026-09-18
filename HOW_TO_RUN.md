# How to Run API Sentinel

---

## Prerequisites
- Python 3.10+ installed
- Terminal / Command Prompt

---

## Method 1: Quick Start (Recommended for Windows)

### 1. One-Time Setup (if `.venv` is not created yet)
Open Command Prompt / PowerShell in the project directory:
```bash
python -m venv .venv
.\.venv\Scripts\pip install -e .
```

### 2. Start Everything & Launch Demo
Double-click or run the batch script:
```cmd
start_all.cmd
```
*This automatically starts the API server, starts the Dashboard, injects validation issues, and opens your web browser.*

### 3. Generate / Push Issues Again (During Demo)
To simulate live traffic and force schema validations, run:
```cmd
push_issues.cmd
```

### 4. Stop All Services
When you are done testing, you can cleanly stop all background servers by running:
```cmd
stop_all.cmd
```

---

## Method 2: Manual Terminal Commands

### Step 1: Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install all dependencies (FastAPI, SQLAlchemy, etc.)
pip install -e .
```

### Step 2: Start Demo API (Terminal 1)
```bash
uvicorn example_app:app --reload --host 127.0.0.1 --port 8000
```

### Step 3: Start Dashboard (Terminal 2)
```bash
uvicorn dashboard.app:app --reload --host 127.0.0.1 --port 8001
```

### Step 4: Run Validation & Push Issues (Terminal 3)
```bash
python push_to_dashboard.py
```

### Step 4 (Alternative): Test Manually with PowerShell
If you prefer to manually generate live traffic instead of using the python script, run these commands in PowerShell:

**Trigger a WARNING Drift (Extra Field):**
```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/users/42"
```

**Trigger an ERROR Drift (Missing Required Field):**
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/auth/login" -Headers @{"Content-Type"="application/json"} -Body '{"username": "alice", "password": "secret"}'
```

**Trigger a CLEAN Request (Passed):**
```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/users"
```

---

## Where to Find Everything

### 1. The Dashboard (Visual Interface)
Once the `dashboard.app` server is running, open your web browser and go to:
👉 **[http://127.0.0.1:8001](http://127.0.0.1:8001)**
Here you will see the real-time API monitoring interface, endpoint health, and schema validation errors.

### 2. The Monitored API (Swagger UI)
To see the actual endpoints that API Sentinel is monitoring, go to:
👉 **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**
This is the standard FastAPI Swagger interface for the dummy application.

### 3. The Database (Persistent Storage)
API Sentinel automatically saves all reports and schema drifts to a local SQLite database, meaning your data won't be lost when you restart the servers!
- **Database File:** Look for a file named `sentinel.db` in the root folder of this project (`g:\Projects\API_sentinel\sentinel.db`).
- **How to view it:** You can open this file using any free SQLite viewer (like [DB Browser for SQLite](https://sqlitebrowser.org/) or [DBeaver](https://dbeaver.io/)). 
- **Tables inside:** 
  - `validation_reports`: Contains the HTTP methods, status codes, and the masked request/response JSON payloads.
  - `differences`: Contains specific error messages and schema drifts linked to each report.

---

## Presentation / Demo Steps for Faculty

1. **Open Swagger UI:** Go to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to show the monitored API endpoints and OpenAPI schema.
2. **Open Dashboard:** Go to [http://127.0.0.1:8001](http://127.0.0.1:8001) to present the real-time API monitoring interface.
3. **Trigger Validation Issues:** Run `push_issues.cmd` or `python push_to_dashboard.py`.
4. **Show Live Results:** Refresh the Dashboard to showcase:
   - Request & response schema validation errors
   - Performance & latency metrics
   - Detailed issue breakdowns and logs
5. **Show Database Persistence:** 
   - Close the dashboard server (`Ctrl + C` or `stop_all.cmd`).
   - Open `sentinel.db` in *DB Browser for SQLite* to prove the logs were permanently saved (and show that sensitive fields like "password" are `***MASKED***`).
   - Restart the dashboard to prove the historical data instantly reappears.
6. **Stop Services:** Run `stop_all.cmd` or press `Ctrl + C` in the terminals.

---

## How to Add and Monitor a New Endpoint

Because the `APISentinelMiddleware` is attached globally in `example_app.py`, any new API endpoint you create is instantly monitored in real-time. No extra configuration is needed for the Python code!

### Step 1: Add the Code (`example_app.py`)
Create your new route just like any normal FastAPI endpoint:
```python
@app.get("/api/v1/orders", tags=["orders"])
async def get_orders():
    # Because of the middleware, this is automatically monitored!
    return JSONResponse(content={"order_id": 123, "status": "shipped"})
```

### Step 2: Add the Schema (`openapi.yaml`)
API Sentinel needs to know what the "correct" data should look like. Document this new endpoint in `openapi.yaml`:
```yaml
paths:
  /api/v1/orders:
    get:
      summary: Get list of orders
      responses:
        '200':
          description: A list of orders
          content:
            application/json:
              schema:
                type: object
                required: [order_id, status]
                properties:
                  order_id:
                    type: integer
                  status:
                    type: string
```

### Step 3: Test It
1. Use Postman, your browser, or PowerShell (`Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/orders"`) to trigger the new API.
2. The middleware will intercept the response (`{"order_id": 123, "status": "shipped"}`) and compare it against the YAML.
3. Refresh the Dashboard! 
   - If they match, it passes (or is ignored if selective persistence is on).
   - If you later modify the Python code to return `{"tracking_number": "XYZ"}`, the dashboard will immediately alert you with an `EXTRA_FIELD` drift warning!
