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

## Web UI

The React UI is served by the same Flask app at `GET /`, so one container
serves both the calculator and the API. It is a build artifact: a fresh clone
has no bundle until you build it.

```bash
make web-install   # npm ci in web/
make web-build     # outputs to public/, served by Flask at /
make dev           # open http://localhost:8080
```

For UI work with hot reload, run Flask and Vite side by side. Vite proxies
`/api` and `/healthz` to Flask on port 8080:

```bash
make dev           # terminal 1: Flask on :8080
make web-dev       # terminal 2: Vite on :5173
```

What the UI does:

- Reads `GET /api/v3/config` so the page states the real limits and pricing
  rules of the running server instead of hardcoding them.
- Uploads with `POST /api/v3/upload` and renders one row per page: coverage
  bars for colour and B&W ink, the model's base price, the B&W price, the
  colour premium, and the final page price.
- Sorts and filters pages (by number, price, or ink coverage), and expands any
  row to show the raw numbers behind its price.

The API key is entered in the page and kept in `localStorage` for that browser
only. It is sent as the `api-key` header on each upload; nothing is stored
server-side.

`make check` runs the full local gate: lint, backend tests, and the frontend
typecheck plus build.

## Deploy to Dokploy

This repository includes `docker-compose.yml` for Dokploy's Compose deployment
mode. The service builds from the existing Dockerfile, listens on port `8080`,
and reports readiness through `GET /healthz`.

1. Push this repository to the Git provider connected to Dokploy.
2. In Dokploy, create a project and add a Compose deployment pointing to this
   repository.
3. Set at least `API_KEY` in Dokploy's environment variables. The service
   rejects every upload when `API_KEY` is empty.
4. Optionally override `MAX_CONTENT_LENGTH`, `MAX_PAGES`, `PRICE_STEP`,
   `PRICE_CAP`, `PRICE_FLOOR_BW`, and `PRICE_FLOOR_COLOR`.
5. Deploy, then route your Dokploy domain or proxy to the
   `api-model-regression` service on port `8080`.

For a local Compose check:

```bash
cp .env.example .env
# Set a real API_KEY in .env, then:
docker compose up --build
curl http://localhost:8080/healthz
```

`PRICE_CAP` accepts an empty string to disable the per-page cap. Set it as
empty in Dokploy rather than omitting it if you need cap-free pricing.

## API Reference

### `POST /api/v3/upload`

Upload a PDF and get pricing estimate.

**Headers:**
- `api-key: <your-api-key>` (required)

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
| `ARTIVITY_SERVER_URL` | (none) | Base URL of the Artivity server for operator auth/labeling |
| `PRINT_PRICING_SERVICE_TOKEN` | (none) | Service token used to call the Artivity server `/internal/train` endpoint |
| `OPERATOR_SESSION_SECRET` | (none, dev fallback) | Flask `secret_key` for operator browser sessions — **required in production** |
| `MODEL_CACHE_TTL_SECONDS` | `60` | TTL for the active pricing model fetched from the Artivity server |
| `OPERATOR_COOKIE_SECURE` | `true` | Set `SESSION_COOKIE_SECURE` for operator cookies |

**Production requirement:** `OPERATOR_SESSION_SECRET` must be set to a stable,
cryptographically random value. The gunicorn deployment uses 2 workers; if the
secret falls back to `os.urandom(32)`, each worker starts with a different key
and operator sessions will break across requests.

### Operator labeling & retrain

Operators log in via the Artivity server OAuth2 flow (`/oauth/authorize` and
`/oauth/token`). The `login` route is intentionally exempt from the
`X-Requested-With` CSRF header because the user is not yet authenticated; this
login-CSRF posture is accepted by product. After login, the service stores an
operator session cookie signed with `OPERATOR_SESSION_SECRET`.

- Samples and labels live on the Artivity server; this service does not keep a
  labeling database.
- `POST /internal/train` accepts an `Authorization: Bearer <service token>`
  request from the Artivity server and retrains the additive isotonic model on
  the latest sample/label set.
- After retraining, the active model is cached for `MODEL_CACHE_TTL_SECONDS`
  before the next fetch from the Artivity server.
- A baked fallback model (`pricing_model_data.py`) is always available so the
  upload endpoint continues to work even if the Artivity server is unreachable.

### `GET /api/v3/config`

Public limits and pricing rules used by the web UI. Never includes `API_KEY`.

```json
{
  "max_pages": 500,
  "max_content_length": 52428800,
  "price_step": 250,
  "price_cap": 3000,
  "price_floor_bw": 300,
  "price_floor_color": 500
}
```

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

## Operator labeling & retrain

The `/api/v3/upload` flow stays the default customer view. An owner-only
`#/operator` hash route adds a small in-app console for retraining the
pricing model without a redeploy.

- **Access**: owner accounts only. Log in with the same email/password used in
  the main Artivity system; the service proxies to `artivity-server` and
  rejects non-owners with `403`.
- **Flow**: upload a sample PDF → review per-page coverage thumbnails → enter
  the real price the owner would quote → repeat across samples → trigger
  retrain → preview MAE / p95 / max-error metrics → activate (hot-swap) or
  dismiss the candidate.
- **Rollback**: every activation pushes a new active model version; activating
  any other version switches back instantly without a redeploy. The runtime
  caches the active model per process for `MODEL_CACHE_TTL_SECONDS` and
  always serves the last known model if `artivity-server` is unreachable.
- **Required env vars** (Dokploy): `ARTIVITY_SERVER_URL`,
  `PRINT_PRICING_SERVICE_TOKEN`, `OPERATOR_SESSION_SECRET`,
  `MODEL_CACHE_TTL_SECONDS`, `OPERATOR_COOKIE_SECURE`. The session secret
  **must** be a stable, random value in production — `app.secret_key` falls
  back to `os.urandom(32)`, which is per-process and breaks operator
  sessions across gunicorn's 2 workers if unset.
