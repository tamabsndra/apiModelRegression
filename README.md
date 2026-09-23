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

### `GET /healthz`

Health check. Returns `{"status": "ok"}`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (empty = reject all) | API authentication key |
| `UPLOAD_FOLDER` | `uploads` | Temp upload directory |
| `MAX_CONTENT_LENGTH` | `16777216` (16 MB) | Max upload size |
| `PRICE_COEFF_COLOR` | `4.2` | Color coverage coefficient |
| `PRICE_COEFF_BW` | `1.8` | BW coverage coefficient |
| `PRICE_INTERCEPT` | `150` | Base price intercept |
| `PRICE_STEP` | `250` | Ladder rounding step (0=off) |
| `PRICE_CAP` | `3000` | Max price cap (empty=off) |
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
| Color coefficient | 4.2 | Linear regression fit |
| BW coefficient | 1.8 | Linear regression fit |
| Intercept | 150 | Linear regression fit |
| R² | 0.964 | Training set fit quality |
| MAE | ~180 IDR | Mean absolute error on test set |

### Ladder Rules

- Prices round UP to the nearest `PRICE_STEP` (default 250 IDR)
- `PRICE_STEP=0` disables rounding
- `PRICE_CAP` caps total price (empty = no cap)
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