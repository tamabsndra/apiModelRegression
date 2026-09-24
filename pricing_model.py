"""Additive isotonic pricing model.

latent = INTERCEPT + f_print(print_area_pct) + f_color(color_area_pct)

Both f_print and f_color are monotone non-decreasing step functions, so the
latent price never decreases when more ink is added. Coefficients live in the
generated artifact pricing_model_data.py; refit with `python3 tools_fit_model.py`.
"""

import numpy as np

from pricing_model_data import (
    COLOR_AREA_THRESHOLDS,
    COLOR_AREA_VALUES,
    INTERCEPT,
    PRINT_AREA_THRESHOLDS,
    PRINT_AREA_VALUES,
)


def latent_price(print_area_pct, color_area_pct):
    """Latent (pre-ladder) price in IDR for one page.

    Args:
        print_area_pct: total ink coverage as a percentage (0-100).
        color_area_pct: colour ink coverage as a percentage (0-100).

    Values outside the fitted range are clipped to the nearest fitted knot.
    """
    print_term = np.interp(print_area_pct, PRINT_AREA_THRESHOLDS, PRINT_AREA_VALUES)
    color_term = np.interp(color_area_pct, COLOR_AREA_THRESHOLDS, COLOR_AREA_VALUES)
    return float(INTERCEPT + print_term + color_term)
