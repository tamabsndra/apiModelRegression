"""Runtime access to the active pricing model with a baked fallback.

Fetches the active model from artivity-server, caches it per version with a
short TTL, and degrades to the last known model or the baked artifact so the
price path never fails.
"""

import time

import artivity_client
from config import Config
from pricing_model_data import (
    COLOR_AREA_THRESHOLDS,
    COLOR_AREA_VALUES,
    INTERCEPT,
    PRINT_AREA_THRESHOLDS,
    PRINT_AREA_VALUES,
)

_cache = {"model": None, "version_id": None, "fetched_at": 0.0}


def baked_model():
    return {
        "intercept": INTERCEPT,
        "print_thresholds": list(PRINT_AREA_THRESHOLDS),
        "print_values": list(PRINT_AREA_VALUES),
        "color_thresholds": list(COLOR_AREA_THRESHOLDS),
        "color_values": list(COLOR_AREA_VALUES),
    }


def _normalize(data):
    return {
        "intercept": float(data["intercept"]),
        "print_thresholds": list(data["print_thresholds"]),
        "print_values": list(data["print_values"]),
        "color_thresholds": list(data["color_thresholds"]),
        "color_values": list(data["color_values"]),
    }


def reset_cache():
    _cache.update(model=None, version_id=None, fetched_at=0.0)


def get_active_model(force=False):
    now = time.monotonic()
    fresh = now - _cache["fetched_at"] < Config.MODEL_CACHE_TTL_SECONDS
    if not force and _cache["model"] is not None and fresh:
        return _cache["model"]
    try:
        data = artivity_client.get_active_model()
        if data:
            model = _normalize(data)
            _cache.update(model=model, version_id=data.get("id"), fetched_at=now)
            return model
    except Exception:
        pass
    if _cache["model"] is not None:
        return _cache["model"]
    return baked_model()
