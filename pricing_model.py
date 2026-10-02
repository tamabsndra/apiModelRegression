"""Latent price from an explicit model dict (see model_store.baked_model)."""

import numpy as np


def latent_price(model, print_area_pct, color_area_pct):
    print_term = np.interp(print_area_pct, model["print_thresholds"], model["print_values"])
    color_term = np.interp(color_area_pct, model["color_thresholds"], model["color_values"])
    return float(model["intercept"] + print_term + color_term)
