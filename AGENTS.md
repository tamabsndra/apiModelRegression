# apiModelRegression — AGENTS.md

PDF print pricing microservice. Estimates print price (IDR) from color/BW coverage using linear regression with ladder rounding.

## Quick Commands

```bash
make dev          # Flask dev server on :8080
make test         # pytest tests/ -v
make lint         # ruff check + format --check
make docker-build # docker build -t apimodelregression:dev .
```

Single test: `pytest tests/test_file.py::TestClass::test_method -v`

Required order: `make lint` → `make test` → `make docker-build`

## Architecture

**App factory** (`app.py:create_app`): Flask app created via factory pattern, loads config from `config.py`, registers routes from `routes.py`.

**Routes** (`routes.py`): Single endpoint `POST /api/v3/upload` accepts multipart PDF with `api-key` header. Validates PDF via magic bytes, enforces `MAX_PAGES`, extracts coverage metrics, calls `pricecounter.getprice()`. Health check at `GET /healthz`. Startup janitor in `app.py` removes orphan uploads older than 1 hour.

**Pricing model** (`pricing.py`): Linear regression formula `price = coeff * (coverage * 100) + intercept`. Applies floors (300 BW, 500 color), ladder rounding to nearest `PRICE_STEP` (default 250), then optional per-page cap.

**Price counter** (`pricecounter.py`): Single metrics module — renders PDF pages at 300 DPI via pypdfium2 (`render_page`), classifies pixels as monochrome (R==G==B, white excluded) or color (`classify_pixels`), computes coverage ratios (`analyze_page`), and sums per-page prices (`getprice`).

## Key Conventions

- **Env vars**: `API_KEY` (fail-closed if empty), `PRICE_COEFF_COLOR=19.59733806`, `PRICE_COEFF_BW=7.05360083`, `PRICE_INTERCEPT=191.3642`, `PRICE_STEP=250` (nearest-ladder), `PRICE_CAP=3000` (per page, empty=off), `PRICE_FLOOR_BW=300`, `PRICE_FLOOR_COLOR=500`, `MAX_PAGES=500`
- **API contract**: UUID-based file uploads only, HMAC constant-time comparison for API keys (latin-1 bytes), JSON response `{price, page, bw_price}`; `413 too_many_pages` when the PDF exceeds `MAX_PAGES`
- **Ladder rules**: Prices round to the NEAREST step (not up), floors guarantee minimums, cap applies per page only — no grand-total cap (page-count proportionality)

## Testing Approach

Synthetic PDF fixtures via Pillow — no real PDF files needed. Tests cover pixel classification (monochrome vs color), pricing edge cases (zero coverage, high coverage, cap applied), API validation (missing key, non-PDF, valid uploads).

## Deployment

Docker image for Fly.io. Port 8080, gunicorn with 2 workers, healthcheck on `/healthz`. See `fly.toml` for config.

## Common Pitfalls

- Hardcoded API key must be removed — use env var
- Debug mode off in production
- Content-Length None handling in request validation
- PRICE_STEP default 250, not 0
- Floors are 300 (BW) and 500 (color)
