# apiModelRegression

PDF print pricing service. Estimates print price (IDR) from color/BW coverage using linear regression with ladder rounding.

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
| `PRICE_COEFF_COLOR` | `19.59733806` | Color coverage coefficient |
| `PRICE_COEFF_BW` | `7.05360083` | BW coverage coefficient |
| `PRICE_INTERCEPT` | `191.3642` | Base price intercept |
| `PRICE_STEP` | `250` | Ladder rounding to nearest step (0=off) |
| `PRICE_CAP` | `3000` | Per-page price cap (empty=off) |
| `PRICE_FLOOR_BW` | `300` | Minimum BW price |
| `PRICE_FLOOR_COLOR` | `500` | Minimum color price |

## Model Documentation

### Algorithm

1. Render each PDF page at 300 DPI
2. Classify each pixel: monochrome if R==G==B, else color
3. Compute coverage ratios (color%, BW%)
4. Apply linear regression: `price = coeff * (coverage * 100) + intercept`
5. Apply floors, ladder rounding, and cap

### Coefficients

| Parameter | Value | Source |
|-----------|-------|--------|
| Color coefficient | 19.59733806 | Linear regression fit |
| BW coefficient | 7.05360083 | Linear regression fit |
| Intercept | 191.3642 | Linear regression fit |
| R2 | 0.9529 | Dataset fit quality (n=1102) |
| MAE | ~107.5 IDR | Mean absolute error on dataset |

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