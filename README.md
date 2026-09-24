# apiModelRegression

PDF print pricing service. Estimates print price (IDR) from color/BW coverage
using an additive isotonic model with ladder rounding.

## Quickstart

```bash
cp .env.example .env
# Edit .env with your API_KEY
make dev
# Server runs on http://localhost:8080
```

## API Reference

### `POST /api/v3/upload`

Upload a PDF and get pricing estimate.

**Headers:**
- `X-API-Key: <your-api-key>` (required)

**Body:** `multipart/form-data` with field `file` (PDF)

**Response (200):**
```json
{
  "price": 2500,
  "page": 3,
  "bw_price": 750
}
```

**Errors:**
| Code | Status | Meaning |
|------|--------|---------|
| `unauthorized` | 401 | Missing or invalid API key |
| `bad_request` | 400 | Invalid PDF or missing file |
| `payload_too_large` | 413 | File exceeds MAX_CONTENT_LENGTH |
| `too_many_pages` | 413 | PDF exceeds MAX_PAGES |

### `GET /healthz`

Health check. Returns `{"status": "ok"}`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (empty = reject all) | API authentication key |
| `UPLOAD_FOLDER` | `uploads` | Temp upload directory |
| `MAX_CONTENT_LENGTH` | `52428800` (50 MB) | Max upload size |
| `MAX_PAGES` | `500` | Max pages per PDF (413 `too_many_pages` beyond) |
| `PRICE_STEP` | `250` | Ladder rounding to nearest step (0=off) |
| `PRICE_CAP` | `3000` | Per-page price cap (empty=off) |
| `PRICE_FLOOR_BW` | `300` | Minimum BW price |
| `PRICE_FLOOR_COLOR` | `500` | Minimum color price |

## Model Documentation

### Algorithm

1. Render each PDF page at 300 DPI
2. Classify each pixel: monochrome if R==G==B, else color
3. Compute coverage ratios (color%, BW%)
4. Evaluate the additive isotonic model:
   `latent = INTERCEPT + f_print(print_area_pct) + f_color(color_area_pct)`
5. Apply floors, ladder rounding, and cap

### Model

`f_print` and `f_color` are monotone non-decreasing step functions fitted by
isotonic regression, so adding ink to a page can never lower its price. The
intercept and both step functions are stored in `pricing_model_data.py`, which
is generated — refit it with:

```bash
python3 tools_fit_model.py
```

| Metric | Value | Notes |
|--------|-------|-------|
| Bucket accuracy | 81.7% | Predicted price equals dataset price |
| MAE | 49.7 IDR | On dataset (n=1102), after ladder rounding |
| R2 | 0.9767 | Dataset fit quality |
| 10-fold CV accuracy | 79.0% | Out-of-sample, mean over 5 seeds |

The previous linear model scored 58.1% CV accuracy / 109.0 IDR CV MAE on the
same features. `tests/test_dataset.py` pins the new floors so a regression to
the linear form fails CI.

**Caveat on the dataset.** Prices in `new-dataset.csv` are all multiples of
250 IDR, i.e. they are outputs of an earlier pricing pipeline rather than
independently quoted prices. The metrics above therefore measure agreement with
that pipeline, not commercial accuracy. The dataset also contains 1561
monotonicity violations (a page with more ink quoted cheaper than one with
less). Treat these figures as a regression guard, not as a business guarantee.

### Ladder Rules

- Prices snap to the NEAREST `PRICE_STEP` multiple (default 250 IDR), never below the floor
- `PRICE_STEP=0` disables rounding
- `PRICE_CAP` applies per page (empty = no cap); there is no grand-total cap
- Floors guarantee minimum prices: 300 IDR (BW), 500 IDR (color)

## Development

```bash
make test     # Run tests
make lint     # Lint with ruff
make docker-build  # Build Docker image
```

## Deployment

Docker image designed for Fly.io. See `fly.toml` for configuration.

```bash
fly deploy
```