"""Service-to-service training endpoint."""

import hmac
from types import SimpleNamespace

from flask import current_app, jsonify, request

from model_fit import evaluate, fit


def _authorized():
    expected = current_app.config.get("PRINT_PRICING_SERVICE_TOKEN", "")
    if not expected:
        return False
    given = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def _eval_config():
    raw = current_app.config.get("PRICE_CAP_RAW", "")
    cap = None if raw in ("", None) else int(raw)
    return SimpleNamespace(
        PRICE_STEP=current_app.config["PRICE_STEP"],
        PRICE_FLOOR_BW=current_app.config["PRICE_FLOOR_BW"],
        PRICE_FLOOR_COLOR=current_app.config["PRICE_FLOOR_COLOR"],
        PRICE_CAP=cap,
    )


def register(app):
    @app.post("/internal/train")
    def train():
        if not _authorized():
            return jsonify({"error": "forbidden", "detail": "invalid service token"}), 403
        body = request.get_json(silent=True) or {}
        rows = body.get("rows") or []
        if not rows:
            return jsonify({"error": "bad_request", "detail": "no rows"}), 400

        try:
            model = fit(rows)
        except (ValueError, KeyError, TypeError) as err:
            return jsonify({"error": "bad_request", "detail": f"malformed rows: {err}"}), 400

        metrics = evaluate(model, rows, _eval_config())
        return jsonify({"data": {**model, "metrics": metrics}})
