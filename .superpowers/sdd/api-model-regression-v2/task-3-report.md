# Task 3 Report: Security hardening — UUID uploads, input validation, error envelope

**Status:** DONE

**Commits:**
- `d7e195f` — fix: UUID uploads, PDF validation, error envelope, disable debug

## Changes made

### 1. UUID filename generation
Replaced `secure_filename(file.filename)` with `uuid.uuid4().hex` + original extension. Prevents path traversal and filename collisions.

### 2. Content-length validation
Added `@app.before_request` hook that safely handles `request.content_length` being `None` (the original code would crash on `None > int`). Uses `Config.MAX_CONTENT_LENGTH` instead of hardcoded 50 MB. Returns 413 with error envelope.

### 3. PDF content validation
Added `validate_pdf()` function that:
- Checks magic bytes (`%PDF-`)
- Opens with `pypdfium2` to verify the PDF is parseable and has pages
- Cleans up the file on failure via `os.unlink`
- Called after save, before price processing

### 4. Unified error envelope
All error responses now use `{"error": "<code>", "detail": "<human message>"}`:
- `bad_request` (400)
- `unauthorized` (401)
- `payload_too_large` (413)
- `invalid_pdf` (400)
- `internal_error` (500)

Added `@app.errorhandler` for 400, 401, 413, 500.

### 5. Debug mode disabled
Changed `app.run(debug=True)` to `app.run(debug=False)`.

### 6. Config integration
- Imported `Config` from `config.py`
- Removed hardcoded API key (`app.api_key = "fD9BkZUwQpVgxw7zLsC3YK9eF6u5J2mN"`)
- Uses `Config.API_KEY`, `Config.UPLOAD_FOLDER`, `Config.MAX_CONTENT_LENGTH`
- Fail-closed: if `Config.API_KEY` is empty, all requests are rejected with 401

### 7. Constant-time API key comparison
Replaced `!=` with `hmac.compare_digest()` to prevent timing attacks.

## Test summary
- Python syntax compilation check passed (`py_compile`)
- All 7 requirements from the task brief implemented
- No refactoring into app factory (deferred to Task 4 as instructed)

## Concerns
None.
