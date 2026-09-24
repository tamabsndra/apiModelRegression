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

**On the dataset.** Prices in `new-dataset.csv` come from the print shop owner
pricing sample PDF pages by hand — this was the manual process the service
replaces. That makes the dataset a genuine record of the business's prices, with
two properties worth knowing:

- Every price is either the 300 IDR B&W floor or a multiple of 250 IDR. The
  owner quotes on the same ladder the service rounds to.
- Manual pricing is not perfectly self-consistent: 0.44% of dominance pairs
  (2502 of 570142) quote a page with more ink at a lower price than one with
  less, involving 254 of 1102 pages. The largest such gap is 750 IDR.

A 1-nearest-neighbour predictor — which can only repeat prices already in the
data — scores 81.6% accuracy / 57.8 IDR MAE, so no model can do much better on
this dataset. The fitted model scores 81.7% / 49.7 IDR, i.e. it matches that
ceiling while staying smooth and monotone. Read the metrics as agreement with
the owner's manual pricing, not as absolute accuracy against a spec.

**Known limitation: B&W pages with heavy ink.** Only 73 of 1102 pages have no
colour, and they span just 0.37%-7.89% ink coverage, all priced at the 300 IDR
floor. Above roughly 8% ink the B&W price curve is therefore extrapolated from
colour-bearing pages rather than fitted from observed B&W quotes. If the shop
needs reliable B&W pricing for ink-heavy documents, ask the owner to quote a
set of pure-B&W samples across the coverage range and refit.
