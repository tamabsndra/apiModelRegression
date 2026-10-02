# apiModelRegression v2.1 Pricing Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Restore correct pricing semantics (per-page sum, white pixels excluded, single intercept, correct floors) that were broken in the v2 refactor, plus reliability fixes (MAX_PAGES, orphan janitor, non-ASCII header) and structure cleanup (dead/duplicated modules, stale docs).

**Architecture:** Per-page pricing: each page's coverage feeds the regression once; page prices are summed. Floors 300 (BW page) / 500 (color page) apply to the page total, intercept counted once, ladder = nearest multiple of PRICE_STEP (never below floor), cap applies per page and to the grand total.

**Spec:** This plan is the authority (addendum to docs/superpowers/specs/2026-09-22-api-model-regression-v2-design.md; where they conflict, this plan wins — it fixes regressions that spec's code snippets introduced).

## Global Constraints

- Empirical truth (verified): blank 1-page PDF must price 300; blank 3-page must price 900; price must scale with page count for identical pages.
- White pixels (255,255,255) are NOT ink: bw_area = mono AND not-white. A blank page has bw_coverage 0.0, color_coverage 0.0.
- Per-page model (v1 semantics): raw = 191.3642 + color_area*19.59733806 + print_area*7.05360083 where print_area = color_area + bw_area (percentages 0-100).
- Floor per page: 300 if color_area == 0 else 500. Applied BEFORE ladder snap; snapped value never below floor.
- Ladder: nearest multiple of PRICE_STEP (not ceil). PRICE_STEP=0 disables. PRICE_CAP caps per-page price and grand total.
- API contract unchanged: {message, price, page, bw_price}. bw_price = 300 * page (v1 semantics, documented as "minimum B&W estimate").
- hmac.compare_digest must receive bytes (latin-1, errors="replace") — non-ASCII header → 401, never 500.
- MAX_PAGES config (default 500): enforced during validate; over-limit → 413 {"error": "too_many_pages"}.
- Orphan janitor: on create_app, delete files in UPLOAD_FOLDER older than 1 hour.
- Delete regression.py and pdfmetrics.py; pricecounter.py is the single metrics module; tests import from pricecounter.
- Update AGENTS.md and README env tables: actual defaults COEFF_COLOR=19.59733806, COEFF_BW=7.05360083, INTERCEPT=191.3642 (note: these are internal; formula lives in pricing.py).
- Config keeps coefficients as env-overridable with those exact defaults.
- All 19 existing tests must be updated where they encode wrong semantics (white-as-bw, calculate_price structure). No test may assert a known-wrong value.

---

### Task A1: Pricing core fix (TDD)

**Files:**
- Modify: `pricing.py` (rewrite calculate_price/ladder_round), `pricecounter.py` (white exclusion + per-page sum), `tests/test_pricing.py`, `tests/test_pdfmetrics.py`

**Steps:**
1. Rewrite tests FIRST to encode correct semantics:
   - classify_pixels: white image → (color=0, bw=0); gray image → bw=100; red → color=100; mixed gray+red → 50/50.
   - ladder nearest: ladder_round(304,250)==300 is WRONG — floor applies before snap in calculate_price; test calculate_price directly:
     - calculate_price(0.0, 0.0) → {"price": 300, "bw_price": 300, "color_price": 300} for a page with no color (floor 300, raw 191)
     - calculate_price(0.0, 0.10) → raw=191.36+7.05*10=261.9 → floor 300 → 300
     - calculate_price(0.0, 0.50) → raw=544 → nearest 250 → 500
     - calculate_price(0.10, 0.90) → print=100 → raw=191.36+19.6*10+7.05*100=1093 → 1000
     - calculate_price(1.0, 0.0) → print=100 → raw=191.36+1959.7+705.4=2856 → ladder 2750? nearest(2856/250)=11.42→11→2750. Then cap 3000 → 2750.
     - cap: with PRICE_CAP=1000 env, calculate_price(1.0,0.0)["price"]==1000
     - PRICE_STEP=0: calculate_price(0.0,0.50)["price"]==544
   - calculate_price signature: (color_coverage, bw_coverage, config=None) — fractions 0-1; returns dict with price/bw_price/color_price where bw_price and color_price are the per-page decomposition (bw component = price with color_coverage=0 — document this in docstring; simplest correct impl: compute page price from full formula; bw_price = price computed with color forced 0; color_price = price - bw_price... NO — keep it simple and honest: bw_price = floor/snapped BW-only price (what the page would cost in pure B&W), color_price = price - bw_price may be negative → instead: color_price key = price computed with bw_coverage forced 0 minus intercept? OVER-ENGINEERING. Decision: return {"price": page_price, "bw_price": bw_only_price, "color_price": max(0, page_price - bw_only_price)} where bw_only_price = page price with color_coverage=0.0.
   - Dataset regression test (tests/test_dataset.py): load data/new-dataset.csv; for each row call calculate_price(color_area/100, bw_area/100) with PRICE_STEP=250, CAP=3000 env defaults; assert MAE vs price column <= 130 and R2 >= 0.90. (Rows where dataset price==300 with color==0: our floor yields 300 ✓.)
2. Run: pytest tests/test_pricing.py tests/test_dataset.py — must FAIL against current code.
3. Rewrite pricing.py: ladder_round = nearest ((round(price/step)*step) with step<=0 → int(price)); calculate_price implements per-page formula with single intercept, floor-then-snap-never-below-floor, cap.
4. Rewrite pricecounter.py classify_pixels: is_mono = (r==g)&(g==b); is_white = (r==255)&(g==255)&(b==255); bw = mono AND NOT white. getprice: price = sum over pages of calculate_price(color_cov_i, bw_cov_i)["price"]; return int total. Keep getpage.
5. Run full pytest — all pass.
6. Commit: "fix: restore per-page pricing semantics, exclude white pixels, nearest-ladder"

### Task A2: Reliability + structure cleanup

**Files:**
- Modify: `config.py` (MAX_PAGES), `routes.py` (hmac bytes, MAX_PAGES enforcement), `app.py` (orphan janitor), delete `regression.py` + `pdfmetrics.py`, update `tests/test_api.py` imports, `AGENTS.md`, `README.md`

**Steps:**
1. config.py: MAX_PAGES = int(os.environ.get("MAX_PAGES", "500")).
2. routes.py validate_pdf: return (True, None, page_count) on success; enforce page_count > Config.MAX_PAGES → return jsonify({"error":"too_many_pages","detail":f"Max {Config.MAX_PAGES} pages"}), 413 (unlink file first). hmac: hmac.compare_digest(api_key.encode("latin-1", errors="replace"), Config.API_KEY.encode("latin-1", errors="replace")) — still gated on `not Config.API_KEY`.
3. app.py: in create_app, after makedirs, janitor: for f in listdir(UPLOAD_FOLDER) older than 3600s → os.remove. Guard with try/except (never crash startup).
4. git rm regression.py pdfmetrics.py; tests import from pricecounter (from pricecounter import analyze_page, classify_pixels).
5. grep for "1.8", "150", "4.2" in AGENTS.md/README env tables → replace with actual defaults; document PRICE_STEP=nearest-ladder, MAX_PAGES, floors.
6. Full pytest + ruff check. Commit: "fix: MAX_PAGES, header robustness, orphan janitor; remove dead modules; correct docs"

### Task A3: End-to-end verification

**Steps:**
1. pytest all green; ruff clean.
2. Live smoke via Flask test client or running server: blank 1p → price 300, page 1, bw_price 300; blank 3p → price 900; 33%-black 10p → price == 10 * single-page price; color PDF → price > bw_price equivalent.
3. Dataset test reports MAE and R2 in output — record numbers.
4. Commit any remaining fixes: "test: end-to-end pricing verification"
