# API Sentinel — How to Run the Project

This guide explains how to set up API Sentinel and start the API, Dashboard, and validation issue generator.

---

## 1. Create the Python Virtual Environment

Open a CMD window in the project folder.

Run:

```cmd
py -m venv .venv
```

This creates a virtual environment named `.venv`.

---

## 2. Install the Project

After creating the virtual environment, install the project:

```cmd
.venv\Scripts\python.exe -m pip install -e .
```

### If the project has `requirements.txt` instead

Run:

```cmd
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use the command that matches the project setup.

---

# 3. Start the API

Go to the project folder and double-click:

```text
start_api.cmd
```

A new CMD window should appear.

You should see something similar to:

```text
API Sentinel - Demo API Server

http://127.0.0.1:8000
http://127.0.0.1:8000/docs

Starting Demo API...
```

### Important

**Do NOT close this CMD window.**

The API needs to keep running.

### Test the API

Open this address in your browser:

http://127.0.0.1:8000/docs

If the Swagger UI opens, the API is running correctly.

---

# 4. Start the Dashboard

Now go back to the project folder.

Double-click:

```text
start_dashboard.cmd
```

Another CMD window should appear.

You should see something similar to:

```text
API Sentinel - Dashboard

http://127.0.0.1:8001

Starting Dashboard...
```

### Important

**Do NOT close this CMD window either.**

Now open:

http://127.0.0.1:8001

You should see the API Sentinel Dashboard.

At this point:

```text
API
↓
Port 8000

Dashboard
↓
Port 8001
```

Both CMD windows must remain open.

---

# 5. Create the Validation Issues

Only do this **after both the API and Dashboard are running**.

Go back to the project folder.

Double-click:

```text
push_issues.cmd
```

It will first check the API and Dashboard.

You should see something similar to:

```text
[1/3] Checking Demo API...
      Demo API is OK.

[2/3] Checking Dashboard...
      Dashboard is OK.

[3/3] Running validation scenarios...
```

It then runs:

```text
push_to_dashboard.py
```

This creates the validation issues and sends the results to the Dashboard.

When it finishes, you should see something similar to:

```text
Done! Dashboard has been updated.
http://127.0.0.1:8001
```

---

# 6. Open the Dashboard

Open:

http://127.0.0.1:8001

You should now see the generated validation results/issues.

---

# Complete Running Order

The normal sequence is:

```text
┌─────────────────────┐
│ 1. start_api.cmd    │
└──────────┬──────────┘
           │
           ▼
        API :8000
           │
           │
┌──────────▼──────────┐
│ 2. start_dashboard  │
│       .cmd          │
└──────────┬──────────┘
           │
           ▼
     Dashboard :8001
           │
           │
┌──────────▼──────────┐
│ 3. push_issues.cmd  │
└──────────┬──────────┘
           │
           ▼
   Create validation
       issues
           │
           ▼
      Dashboard
```

## Easy way to remember

Always run these in this order:

```text
① start_api.cmd
        ↓
② start_dashboard.cmd
        ↓
③ push_issues.cmd
```

### Important

Do **not** close the API or Dashboard CMD windows while `push_issues.cmd` is running.

---

# 7. Start Everything Automatically

There is also a fourth CMD file:

```text
start_all.cmd
```

Instead of running the three files manually, you can double-click:

```text
start_all.cmd
```

It is designed to automatically:

1. Start the API
2. Wait until the API is ready
3. Start the Dashboard
4. Wait until the Dashboard is ready
5. Run the issue-generation script
6. Open the Dashboard
7. Open Swagger

### Recommended for a Demo or Presentation

For a quick demo, use:

```text
start_all.cmd
```

### Recommended for Testing Each Part

If you want to understand or test each component separately, use:

```text
start_api.cmd
↓
start_dashboard.cmd
↓
push_issues.cmd
```

---

# 8. If `push_issues.cmd` Fails

There is a known Python-side mismatch involving:

```text
push_to_dashboard.py
```

and the:

```text
/api/v1/users
```

endpoint.

Because of this, it is possible for:

- API check → **OK**
- Dashboard check → **OK**
- `push_issues.cmd` → **FAIL**

If this happens, the problem is likely in the Python code/API endpoint mismatch rather than the CMD files.

---

# Quick Reference

| File | What it does | Port |
|---|---|---:|
| `start_api.cmd` | Starts the API | 8000 |
| `start_dashboard.cmd` | Starts the Dashboard | 8001 |
| `push_issues.cmd` | Creates validation issues | — |
| `start_all.cmd` | Starts everything automatically | 8000 + 8001 |
| `push_to_dashboard.py` | Generates/sends validation results | — |

## URLs

**API / Swagger:**

http://127.0.0.1:8000/docs

**Dashboard:**

http://127.0.0.1:8001

---

# Short Version

If everything is already installed:

```text
start_api.cmd
        ↓
start_dashboard.cmd
        ↓
push_issues.cmd
```

Or, for a quick demo:

```text
start_all.cmd
```

Keep the API and Dashboard CMD windows open while the project is running.
