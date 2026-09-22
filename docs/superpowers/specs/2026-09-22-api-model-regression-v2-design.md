# apiModelRegression v2 Design Spec

## Goal

Perfect the apiModelRegression service: fix critical deployment/security bugs, modernize the codebase, improve model accuracy, and establish engineering foundations (tests, CI, documentation).

## Architecture

Flat structure (no package), app factory pattern, environment-based configuration, gunicorn entrypoint, modernized dependencies (Python 3.13). The service estimates PDF print prices (IDR) from color/BW coverage using a linear regression model with ladder rounding.

## Tech Stack

- Python 3.13
- Flask 3.0.3
- gunicorn (production server)
- pypdfium2, numpy, pillow (PDF processing)
- pytest, ruff (testing/linting)
- GitHub Actions (CI)
- Docker, Fly.io (deployment)

## Requirements

### Phase 0: Hygiene
- Remove committed artifacts: `__pycache__/`, `.DS_Store`, `requirements-copy.txt`, `uploads/upload.img`, `__init__.py`, `templates/`, `Procfile`
- Update `.gitignore` and `.dockerignore` to be comprehensive

### Phase 1: Security & Robustness
- Extract all configuration to environment variables (fail-closed for `API_KEY`)
- Fix race condition: use UUID filenames for uploads
- Handle malformed input: validate `content_length`, PDF content (magic bytes + pypdfium open)
- Unified JSON error envelope `{"error", "detail"}`
- Disable `debug` mode in all paths

### Phase 2: Production Readiness
- App factory pattern: `main.py` (gunicorn entrypoint), `app.py` (factory)
- Fix Dockerfile: `python:3.13-slim`, non-root user, gunicorn entrypoint, healthcheck
- Fix fly.toml port alignment (8080 end-to-end)
- Add `GET /healthz` endpoint
- Remove catch-all `/<name>` route and hello page

### Phase 3: Model Quality
- Fix pixel classification: monochrome = R==G==B (fix channel-vs-mean bug)
- Single-pass numpy: compute color+bw together (save ~26 MB RAM per page)
- Render directly to target resolution (no 144→300 dpi stretch)
- Implement ladder rounding: `PRICE_STEP` (default 250, 0=off), `PRICE_CAP` (default 3000, empty=off)
- Floors: 300 (BW), 500 (color) — guaranteed minimums

### Phase 4: Engineering Foundation
- pytest with synthetic PDF fixtures (Pillow)
- Unit tests: pricing logic, pdfmetrics, API endpoints
- ruff (lint/format) + GitHub Actions CI (ruff → pytest → docker build)
- README: quickstart, API reference, env table, model documentation (coefficients, R²=0.964, MAE, data provenance, ladder rules)
- `.env.example`, Makefile (`dev`, `test`, `lint`, `docker-build`)

## Constraints

- API contract preserved: `POST /api/v3/upload` with `price`/`page`/`bw_price` response fields
- Model coefficients unchanged (near-optimal, re-fit <1% difference)
- No backward compatibility concerns (service not live)
- Python 3.13 (modernize from 3.9 EOL)

## Out of Scope

- Rate limiting
- Async/queue processing for large files
- Model retraining
- Multiple API keys
