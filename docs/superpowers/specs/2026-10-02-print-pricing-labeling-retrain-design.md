# Print Pricing Labeling & Retrain — Design Spec

Date: 2026-10-02
Status: approved for planning
Repos touched: `app/artivity-server` (Go/Postgres), `app/apiModelRegression` (Flask + React)

## Goal

Let the shop **owner** update print-price standards end-to-end without a developer
and without a deploy: upload sample PDFs, label the real price per page, retrain the
pricing model, preview the result, and activate it live. Accounts and data live in
`artivity-server`; `apiModelRegression` becomes the coverage engine, the labeling UI,
and the training/serving runtime.

## Current State

- `apiModelRegression` (Flask) prices a PDF from per-page coverage using an additive
  isotonic model `latent = INTERCEPT + f_print(print_area) + f_color(color_area)`
  (`pricing_model.py:21`). Coefficients are baked into the generated
  `pricing_model_data.py`, produced by `tools_fit_model.py` from `new-dataset.csv`.
- Updating prices today = edit the CSV, run `python3 tools_fit_model.py`, commit and
  redeploy. There is no runtime update path.
- The React web app (`web/`) only uploads a PDF and shows the price.
- `artivity-server` (Go, PostgreSQL, JWT HS256 with shared `JWT_SECRET`, DB-backed RBAC)
  is the system of record. Login is `POST /login`; identity `GET /api/v1/users/me`;
  permissions `GET /api/v1/acl/me`.
- Deployment reality: Dokploy runs the image via `docker-compose.yml`; gunicorn runs
  **2 workers** (`Dockerfile:31`). Any live model state must be persistent and
  re-loadable.

## Scope, Non-goals, Success Criteria

### Success criteria

1. Owner logs in with their `artivity-server` credentials; no separate account.
2. Owner uploads a sample PDF, sees per-page coverage, and enters the real price per page.
3. Owner retrains and sees a preview (row count, mean/max/p95 absolute error, sample pages)
   before activating.
4. Activation is live with no deploy; a rollback to a previous version is available.
5. `POST /api/v3/upload` keeps its contract and serves the active model immediately; it
   still works (fallback to the baked model) when `artivity-server` is unreachable.
6. Per-page pricing semantics are unchanged: floor BW 300 / color 500, ladder 250,
   per-page cap 3000.
7. Go and Python test suites pass; the new migration applies.

### Non-goals

- Own user/password management (accounts come from `artivity-server`).
- Any role other than `owner` may label or retrain.
- Changing the `/api/v3/upload` response shape.
- Changing the pixel/coverage engine or the rounding pipeline semantics.

## Architecture & Boundaries

- `artivity-server` is the **source of truth** and the **orchestrator**: new
  `print_pricing` module owns samples, labels, dataset versions, and model versions.
- `apiModelRegression` is a **stateless compute + UI tier**: proxies owner auth to
  `artivity-server`, computes coverage, trains on request, and serves prices from a
  pull-through cached active model.
- RBAC gate uses **role**, not permission: `WithRoleJWTAuth(..., ["owner"])`. In
  `artivity-server`, seeded permissions are effectively granted to owner/kasir/operator
  (see `docs/system-knowledge/02-roles-permissions.md`), so a permission check would not
  isolate owner.
- Service-to-service auth uses a dedicated token env `PRINT_PRICING_SERVICE_TOKEN`
  (constant-time compare, fail-closed), following the existing `ATTENDANCE_API_KEY`
  pattern in `middleware/apikey.go`.

## Data Model (artivity-server, PostgreSQL)

Conventions follow `db/migrations/20261002033154_create_pos_sync_tables.up.sql`:
`id uuid DEFAULT public.uuidv7()`, `internal_id bigserial UNIQUE`, FKs to
`users(internal_id)`, `timestamp with time zone DEFAULT CURRENT_TIMESTAMP`, `jsonb`.

### `print_pricing_samples`

One uploaded sample document. The raw PDF is **not** stored.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | `uuidv7()` |
| `internal_id` | bigserial UNIQUE | |
| `original_filename` | varchar(255) | |
| `page_count` | integer NOT NULL | |
| `uploaded_by` | integer REFERENCES users(internal_id) ON DELETE SET NULL | |
| `status` | varchar(20) NOT NULL DEFAULT 'labeling' | `labeling` \| `completed` \| `discarded` |
| `created_at`, `updated_at` | timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### `print_pricing_pages`

One row per page.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `internal_id` | bigserial UNIQUE | |
| `sample_id` | uuid REFERENCES print_pricing_samples(id) ON DELETE CASCADE | |
| `page_number` | integer NOT NULL | |
| `bw_area` | double precision NOT NULL | coverage %, 0–100 |
| `color_area` | double precision NOT NULL | coverage %, 0–100 |
| `print_area` | double precision GENERATED ALWAYS AS (bw_area + color_area) STORED | |
| `thumbnail` | bytea | small JPEG (~160px wide), nullable |
| `labeled_price` | integer | real price in IDR, nullable |
| `labeled_by` | integer REFERENCES users(internal_id) ON DELETE SET NULL | |
| `labeled_at` | timestamptz | nullable |
| `created_at`, `updated_at` | timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP | |

`UNIQUE (sample_id, page_number)`.

### `print_pricing_dataset_versions`

A frozen snapshot of the labeled pages used for one training run. Retrain uses all
currently labeled, non-discarded pages (replace semantics).

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `internal_id` | bigserial UNIQUE | |
| `row_count` | integer NOT NULL | |
| `created_by` | integer REFERENCES users(internal_id) ON DELETE SET NULL | |
| `note` | text | nullable |
| `created_at` | timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### `print_pricing_dataset_rows`

Frozen values for reproducibility and rollback.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | `uuidv7()` |
| `internal_id` | bigserial UNIQUE | |
| `dataset_version_id` | uuid REFERENCES print_pricing_dataset_versions(id) ON DELETE CASCADE | |
| `page_id` | uuid | provenance only, no FK, so the snapshot survives sample deletion |
| `bw_area`, `color_area`, `print_area`, `price` | double precision NOT NULL | snapshot |
| `created_at` | timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### `print_pricing_model_versions`

Coefficients, metrics, status.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `internal_id` | bigserial UNIQUE | |
| `dataset_version_id` | uuid REFERENCES print_pricing_dataset_versions(id) | |
| `status` | varchar(20) NOT NULL DEFAULT 'candidate' | `candidate` \| `active` \| `archived` |
| `intercept` | double precision NOT NULL | |
| `print_thresholds`, `print_values` | jsonb NOT NULL | isotonic knots |
| `color_thresholds`, `color_values` | jsonb NOT NULL | isotonic knots |
| `metrics` | jsonb NOT NULL DEFAULT '{}'::jsonb | `n_rows`, `mean_abs_error`, `max_abs_error`, `p95_abs_error` |
| `created_by` | integer REFERENCES users(internal_id) ON DELETE SET NULL | |
| `created_at` | timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP | |
| `activated_at` | timestamptz | nullable |
| `activated_by` | integer REFERENCES users(internal_id) ON DELETE SET NULL | |

Single-active invariant:

```sql
CREATE UNIQUE INDEX uq_print_pricing_model_single_active
    ON public.print_pricing_model_versions ((true)) WHERE status = 'active';
```

No seed rows: with no `active` model, `apiModelRegression` falls back to the baked
`pricing_model_data.py`, so behavior is unchanged until the first activation.

## API Surface

Base: `/api/v1/print-pricing`. Owner endpoints use `WithRoleJWTAuth(store, ["owner"])`.

### Owner (JWT owner, called by the SPA through Flask, which forwards the JWT)

| Method | Path | Purpose |
|---|---|---|
| POST | `/samples` | create sample + pages (coverage + thumbnails from Flask) |
| GET | `/samples` | list samples + labeling progress |
| GET | `/samples/{id}` | sample detail + pages |
| DELETE | `/samples/{id}` | delete sample (cascade pages) |
| PATCH | `/pages/{id}` | set `labeled_price` |
| POST | `/dataset-versions` | snapshot all labeled pages |
| GET | `/dataset-versions` / `/dataset-versions/{id}` | list / rows |
| POST | `/retrain` | snapshot + call Flask training + store candidate |
| GET | `/model-versions` | list versions + status + metrics |
| POST | `/model-versions/{id}/activate` | activate (archives current); also serves as rollback |

### Service (header `X-API-Key: <PRINT_PRICING_SERVICE_TOKEN>`, constant-time, fail-closed)

| Method | Path | Where | Purpose |
|---|---|---|---|
| GET | `/active-model` | artivity-server | active coefficients + `version_id` + `updated_at` |
| POST | `/internal/train` | apiModelRegression | fit + metrics from dataset rows |

## Orchestration Flow (Go orchestrates)

1. Owner clicks Retrain in the SPA.
2. Flask `POST /api/label/retrain` forwards to Go `POST /print-pricing/retrain` with the
   owner JWT.
3. Go acquires `pg_try_advisory_lock` (409 if a retrain is already running), snapshots
   all labeled non-discarded pages into a `dataset_version` + rows. The lock is held on a
   dedicated pooled connection for the duration of the run, including the outbound
   training call.
4. Go calls `POST {API_MODEL_REGRESSION_URL}/internal/train` with dataset rows and
   `PRICE_STEP/PRICE_FLOOR_BW/PRICE_FLOOR_COLOR/PRICE_CAP`.
5. Flask fits the additive isotonic model and returns coefficients + metrics (metrics
   computed on the final price after floor/ladder/cap).
6. Go stores a `candidate` model version tied to the dataset version.
7. SPA shows the preview (metrics + sample pages).
8. Owner clicks Activate → Go `POST /model-versions/{id}/activate` in a single
   transaction: archive the current active, set the new one active.
9. Flask's cache becomes stale within `MODEL_CACHE_TTL_SECONDS`; the next price request
   refetches `GET /active-model`.

## apiModelRegression Changes

### Auth & session (Flask)

- `POST /api/label/auth/login` — body `email` + `password`, proxy to `artivity-server`
  `POST /login`. Require role `owner` (from the `user` object / `GET /api/v1/acl/me`);
  non-owner → 403. Store `{token, refresh_token, user_id}` in a signed httpOnly cookie
  (`itsdangerous`, `OPERATOR_SESSION_SECRET`); stateless, consistent across workers.
  Flags: `HttpOnly`, `Secure`, `SameSite=Lax`.
- `GET /api/label/auth/me`, `POST /api/label/auth/logout`.
- Each labeling request forwards `Authorization: Bearer <token>` to `artivity-server`
  (RBAC stays there). On 401, Flask attempts `POST /refresh` once, updates the cookie,
  and retries.
- CSRF: same-origin + `SameSite=Lax`; additionally require a custom `X-Requested-With`
  header on mutating requests.

### Labeling proxy

- `POST /api/label/samples` (multipart PDF): validate PDF (magic bytes, `MAX_PAGES`),
  compute per-page coverage via `pricecounter.analyze_page`, produce small JPEG
  thumbnails, POST to Go `/print-pricing/samples` with the owner JWT.
- `GET /api/label/samples`, `GET /api/label/samples/{id}`, `DELETE /api/label/samples/{id}`,
  `PATCH /api/label/pages/{id}` — thin proxies that forward the JWT.
- `POST /api/label/retrain`, `POST /api/label/model-versions/{id}/activate` — proxies.

### Training (internal)

- Refactor `tools_fit_model.py` into pure functions `fit(rows) -> coefficients` and
  `evaluate(coefficients, rows, params) -> metrics`. The existing CLI still regenerates
  `pricing_model_data.py` as the baked default/fallback.
- `POST /internal/train` (service token): input dataset rows + pricing params; output
  coefficients + metrics.

### Model serving, cache, fallback

- New `model_store.py`: `get_active_model()` with a process cache keyed by `version_id`
  and a short TTL (`MODEL_CACHE_TTL_SECONDS`, default 60); on expiry fetch
  `GET /active-model` using the service token.
- On fetch failure: use the last cached model; if none, fall back to the baked
  `pricing_model_data.py`, so the price path never fails.
- `pricing.py` is refactored so the latent function takes a model object instead of
  module-level constants; `calculate_price` reads from `model_store`. `/api/v3/upload`
  stays unchanged.
- HTTP calls use stdlib `urllib.request` (no new dependency); tests monkeypatch the
  outbound client.
- Multi-worker: per-worker cache; new versions propagate within TTL.

### New Flask config

`ARTIVITY_SERVER_URL`, `PRINT_PRICING_SERVICE_TOKEN`, `OPERATOR_SESSION_SECRET`,
`MODEL_CACHE_TTL_SECONDS` (default 60), `OPERATOR_COOKIE_SECURE` (default true; set
false for local http dev).

### New artivity-server config

`API_MODEL_REGRESSION_URL`, `PRINT_PRICING_SERVICE_TOKEN`, `MIN_TRAINING_ROWS`
(default 20). The min-rows guard is enforced in Go when snapshotting, since Go owns the
retrain flow.

## Web UI

The app is a single-page SPA without a router. Add a hash-routed operator area
(`#/operator`); the public calculator stays the default view. Match the existing
Artivity design system (neu surfaces, ink/blue/rose palette, Nunito/Geist/Questrial),
Indonesian copy.

States:

1. **Login** — email + password → `POST /api/label/auth/login`; non-owner shows a
   "khusus owner" message.
2. **Dashboard** — sample list with labeling progress, "Upload sample", active-model
   card (version + metrics + activated_at), "Retrain", and a model-version history list.
3. **Sample labeling** — per page: thumbnail, coverage BW/color/print (%), real-price
   input (IDR); save per page; progress; delete sample.
4. **Retrain preview** — `n_rows`, `mean/max/p95 abs error`, sample pages (predicted vs
   labeled vs delta); "Aktifkan" / "Batal".
5. **Model versions** — status badge, metrics, timestamp, "Aktifkan versi ini"
   (rollback = activate an older version).

Behavior: opening `#/operator` while logged out shows login (check
`GET /api/label/auth/me`); mutating requests send `X-Requested-With` and use the
same-origin session cookie; upload uses `XMLHttpRequest` for progress (matching
`web/src/lib/api.ts`). Accessibility: explicit form labels, sensible focus order,
sufficient contrast, touch targets >= 44px, errors not conveyed by color alone.

Files: `web/src/App.tsx` (hash routing + gate), `web/src/components/Header.tsx`
(operator link), new `web/src/components/operator/*` (`Login`, `OperatorDashboard`,
`SampleLabeling`, `RetrainPreview`, `ModelVersions`), `web/src/lib/labelApi.ts`,
`web/src/lib/types.ts`.

## Testing Strategy

### artivity-server (Go)

- Migration up/down.
- Store/service tests (test DB): sample/page CRUD, labeling, replace-semantics dataset
  snapshot, candidate creation, activate/archive transitions.
- Invariant: at most one `active` model (partial index + activate path).
- Handler tests: owner allowed; kasir/operator/anonymous → 401/403; service endpoints
  require a valid token and fail closed when missing/wrong.
- Gates: `make lint`, `make test-unit`, `make test-integration`.

### apiModelRegression (pytest)

- Pure unit: `fit` + `evaluate` on small synthetic datasets — monotonicity, metric values.
- `model_store`: cache hit, TTL expiry, fetch failure → last cache, no cache → baked
  fallback, version change invalidates cache.
- Auth/proxy with the Flask test client and a monkeypatched outbound client: login sets a
  signed cookie; non-owner rejected; 401 → refresh once → retry; logout.
- `/internal/train`: reject empty/wrong token (constant-time); valid token returns
  coefficients + metrics.
- Existing tests stay green; pricing tests inject a model object.
- Gates: `make lint`, `make test`, `make web-build` (via `make check`).

### Frontend

`npm run typecheck` + build. No FE test runner exists; rely on typecheck plus a manual QA
checklist. (Vitest can be added later if desired.)

### E2E manual checklist

Owner login → upload sample → label some prices → retrain → review preview → activate →
confirm `/api/v3/upload` uses the new model → rollback → confirm prices revert.

## Rollout & Migration

1. Deploy `artivity-server` (tables + module + endpoints); set
   `API_MODEL_REGRESSION_URL`, `PRINT_PRICING_SERVICE_TOKEN`, `MIN_TRAINING_ROWS`.
2. Deploy `apiModelRegression` (auth proxy, UI, `model_store`, `/internal/train`); set
   `ARTIVITY_SERVER_URL`, the same `PRINT_PRICING_SERVICE_TOKEN`,
   `OPERATOR_SESSION_SECRET`, `MODEL_CACHE_TTL_SECONDS`.
3. `/api/v3/upload` contract never changes. Reverting is safe (tables stay idle).
4. No data migration: `new-dataset.csv` and the baked artifact remain the fallback.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Price path depends on artivity-server | Per-version cache + baked fallback; TTL tunable |
| 2 workers briefly disagree on version | Propagates within TTL (default 60s) |
| Training blocks a worker | Fitting is fast (<1s for ~1–2k rows); gunicorn timeout 120s |
| Wrong operator labels | Preview metrics + sample pages + rollback |
| Thumbnails grow the DB | Cap JPEG dimensions/size; deleted with the sample |
| Token leakage | httpOnly cookie, service token in env, owner-only, CSRF header |
| Revoked token still accepted | Every request re-validated in Go (`token_version`) |

## Decisions & Defaults

- Data lives in `artivity-server` Postgres; `artivity-server` orchestrates.
- Dataset semantics: **replace** (each retrain snapshots all current labeled pages).
- Model activation: live hot-swap via Go, pull-through cache in Flask, baked fallback.
- Access: role `owner` only.
- Owner accounts seeded from `artivity-server`; no separate user management.
- `MIN_TRAINING_ROWS` = 20; thumbnails stored as bytea JPEG (~160px wide).
- Retrain concurrency guarded by `pg_try_advisory_lock` (409 when busy).

## Open Items

1. Inter-service URL: the Dokploy service hostname on the shared Docker network vs the
   public HTTPS domain — pick before deploy.
2. Who provisions `PRINT_PRICING_SERVICE_TOKEN`, `OPERATOR_SESSION_SECRET`, and the
   `MIN_TRAINING_ROWS` value (owner/ops).
3. Thumbnail final dimensions/quality (start ~160px wide, JPEG q70).
