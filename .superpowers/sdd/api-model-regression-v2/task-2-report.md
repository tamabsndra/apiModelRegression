# Task 2 Report: Extract configuration to environment variables

## Status
DONE

## Commits
- `7181618` — feat: extract configuration to environment variables via config.py

## What was done
Created `config.py` with a `Config` class that loads all tunable parameters from environment variables:

| Variable | Default | Notes |
|---|---|---|
| `API_KEY` | `""` (empty) | Fail-closed — empty string if unset |
| `UPLOAD_FOLDER` | `"uploads"` | |
| `MAX_CONTENT_LENGTH` | `52428800` (50 MB) | |
| `PRICE_STEP` | `250` | 0 = off |
| `PRICE_CAP` | `3000` | Empty string = `None` (off) |
| `PRICE_FLOOR_BW` | `300` | |
| `PRICE_FLOOR_COLOR` | `500` | |

**Deliberately excluded** (per task brief correction): `PRICE_COEFF_COLOR`, `PRICE_COEFF_BW`, `PRICE_INTERCEPT` — these remain hardcoded in `regression.py` and will be addressed in a later task.

## Test summary
1. **Primary verification** — `API_KEY=test123 PRICE_STEP=500 python3 -c "from config import Config; c = Config(); print(c.API_KEY, c.PRICE_STEP, c.PRICE_CAP)"` → output: `test123 500 3000` ✓
2. **PRICE_CAP off** — `PRICE_CAP=""` → `c.PRICE_CAP` returns `None` ✓
3. **Defaults** — no env vars set → `API_KEY=''`, `PRICE_CAP=3000`, `PRICE_FLOOR_BW=300`, `PRICE_FLOOR_COLOR=500`, `PRICE_STEP=250`, `UPLOAD_FOLDER='uploads'`, `MAX_CONTENT_LENGTH=52428800` ✓

## Concerns
None.
