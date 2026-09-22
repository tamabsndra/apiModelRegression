# Task 4 Report: App factory pattern and entrypoint separation

**Status:** DONE

**Commits:**
- `870f1a0` — refactor: app factory pattern, main.py entrypoint, routes.py extraction
- `9b7e533` — refactor: remove api_v3.py, superseded by app factory (app.py/main.py/routes.py)

## Changes made

### 1. Created `app.py` with `create_app()` factory
Flask application factory that configures the app from `Config`, creates upload folder, and registers routes.

### 2. Created `main.py` as gunicorn entrypoint
Imports `create_app` and creates the `application` object. Runs on port 8080 when executed directly.

### 3. Extracted routes to `routes.py`
All route definitions moved into `register_routes(app)` function including:
- Upload endpoint (`/api/v3/upload`) with all security fixes preserved
- Health check endpoint (`/healthz`) returning `{"status": "ok"}`
- Error handlers (400, 401, 413, 500)
- Content-length validation via `@app.before_request`

### 4. Removed catch-all route and hello page
Deleted `@app.route("/")` and `@app.route("/<name>")` greeting routes from `api_v3.py`.

### 5. Deleted `api_v3.py`
Replaced with new three-file structure: `app.py`, `main.py`, `routes.py`.

### 6. Preserved all security fixes from Task 3
- UUID filename generation
- PDF content validation (magic bytes + page count)
- Error envelope format
- `hmac.compare_digest` for API key comparison
- Config integration (no hardcoded keys)
- Fail-closed API key validation

## Test summary
Live server run (`API_KEY=testkey123 python3 main.py`, started on port 8080, verified with curl):
- `/healthz` → 200 `{"status": "ok"}`
- `GET /` → 404, `GET /foo` → 404 (catch-all route and hello page removed)
- Upload without API key → 401 `{"error": "unauthorized", ...}` (fail-closed preserved)
- Upload with wrong API key → 401
- Upload of a real 1-page PDF with correct key → 200 `{"message": "File processed", "price": 300, "page": 1, "bw_price": 300}` (full pipeline: UUID save → PDF validation → pricecounter → cleanup)
- Upload of non-PDF file → 400 `{"error": "bad_request", "detail": "File type not allowed"}`
- Python syntax compilation passed (`py_compile`)

## Concerns
- `Dockerfile` still references `FLASK_APP=api_v3.py` (line 14). Left as-is because Dockerfile/fly.toml are explicitly Task 5 scope. Docker image will be broken until Task 5 lands.
