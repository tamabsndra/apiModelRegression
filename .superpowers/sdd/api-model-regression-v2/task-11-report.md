# Task 11 Report — Documentation

## Completed Items

- [x] `.env.example` with all required env vars
- [x] `Makefile` with dev, test, lint, docker-build targets
- [x] `README.md` with quickstart, API reference, env table, model docs, deployment notes

## Files Created/Modified

1. **`.env.example`** — All environment variables documented
2. **`Makefile`** — dev, test, lint, docker-build targets
3. **`README.md`** — Comprehensive documentation including:
   - Quickstart guide
   - API reference (`POST /api/v3/upload`, `GET /healthz`)
   - Environment variable table
   - Model documentation (coefficients, R², MAE, ladder rules)
   - Development commands
   - Deployment notes

## Model Documentation Included

| Parameter | Value | Source |
|-----------|-------|--------|
| Color coefficient | 19.59733806 | Linear regression fit |
| BW coefficient | 7.05360083 | Linear regression fit |
| Intercept | 191.3642 | Linear regression fit |
| R² | 0.964 | Training set fit quality |
| MAE | ~180 IDR | Mean absolute error on test set |

## Ladder Rules Documented

- Prices round UP to nearest PRICE_STEP (default 250 IDR)
- PRICE_STEP=0 disables rounding
- PRICE_CAP caps total price (empty = no cap)
- Floors: 300 IDR (BW), 500 IDR (color)