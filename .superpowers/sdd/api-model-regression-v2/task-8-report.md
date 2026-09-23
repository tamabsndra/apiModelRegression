# Task 8 Report: Implement ladder rounding and price floors

## Status: COMPLETE

## Changes Made

### 1. Created `pricing.py`
- `ladder_round(price, step)` - rounds up to nearest step; step=0 disables
- `calculate_price(color_coverage, bw_coverage, config=None)` - applies linear regression coefficients from `regression.py`, then floors, ladder rounding, and cap
- Uses hardcoded coefficients: intercept=191.3642, color_coeff=19.59733806, print_coeff=7.05360083
- Floors: 300 (BW), 500 (color)
- Cap: configurable via Config.PRICE_CAP

### 2. Updated `routes.py`
- Replaced inline pricing logic with `pricing.calculate_price`
- Removed dependency on `pricecounter.getprice`
- Now uses direct rendering and analysis from `pricecounter.render_page` and `pricecounter.analyze_page`

### 3. Updated `config.py`
- Added PRICE_COEFF_COLOR, PRICE_COEFF_BW, PRICE_INTERCEPT environment variables

### 4. Updated `pricecounter.py`
- Changed `process_page` to return dict from `calculate_price` instead of just price

## Verification
- ladder_round tests passed: 1200->1250, 1000->1000, 1001->1250, 500->500 (disabled)
- Floor tests passed: zero coverage hits BW 300, color 500

## Commit
```
feat: ladder rounding (PRICE_STEP), price cap, floors (BW 300, color 500)
```
</content>