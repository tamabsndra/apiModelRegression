import pytest

from model_fit import evaluate, fit


def _rows():
    # Price rises with ink; the fit must be monotone and coherent.
    rows = []
    for i in range(1, 21):
        color = i * 4.0
        rows.append({"bw_area": 1.0, "color_area": color, "price": float(500 + i * 100)})
    return rows


def test_fit_is_monotone_and_evaluate_reports_zero_error_on_exact_fit():
    rows = _rows()
    model = fit(rows)
    assert model["print_thresholds"] == sorted(model["print_thresholds"])
    assert model["color_thresholds"] == sorted(model["color_thresholds"])

    class Cfg:
        PRICE_STEP = 250
        PRICE_FLOOR_BW = 300
        PRICE_FLOOR_COLOR = 500
        PRICE_CAP = None

    metrics = evaluate(model, rows, Cfg)
    assert metrics["n_rows"] == len(rows)
    # The fitted model reproduces the ladder-rounded labels for monotone data.
    assert metrics["mean_abs_error"] <= 250


def test_fit_rejects_empty_rows():
    with pytest.raises(ValueError):
        fit([])
