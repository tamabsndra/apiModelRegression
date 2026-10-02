"""Pure additive isotonic fitting and evaluation for print pricing.

Both f_print and f_color are monotone non-decreasing step functions:
    latent = INTERCEPT + f_print(print_area) + f_color(color_area)
"""

import numpy as np

TOLERANCE = 1e-9
MAX_ITERATIONS = 5000


def pava(y, w):
    values, weights, counts = [], [], []
    for value, weight in zip(y, w, strict=True):
        values.append(float(value))
        weights.append(float(weight))
        counts.append(1)
        while len(values) > 1 and values[-2] > values[-1]:
            v1, v2 = values.pop(), values.pop()
            w1, w2 = weights.pop(), weights.pop()
            n1, n2 = counts.pop(), counts.pop()
            values.append((v1 * w1 + v2 * w2) / (w1 + w2))
            weights.append(w1 + w2)
            counts.append(n1 + n2)
    return np.repeat(np.array(values), counts)


def isotonic(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    order = np.argsort(x, kind="stable")
    xs, ys = x[order], y[order]
    unique_x, inverse, counts = np.unique(xs, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=ys)
    fitted = pava(sums / counts, counts)
    keep = np.ones(len(fitted), dtype=bool)
    if len(fitted) > 2:
        keep[1:-1] = (fitted[1:-1] != fitted[:-2]) | (fitted[1:-1] != fitted[2:])
    return unique_x[keep], fitted[keep]


def fit_additive(print_area, color_area, price):
    mu = float(price.mean())
    f_print = np.zeros_like(price)
    f_color = np.zeros_like(price)
    knots_print = values_print = knots_color = values_color = None
    for _ in range(MAX_ITERATIONS):
        previous = f_print.copy()
        knots_print, values_print = isotonic(print_area, price - mu - f_color)
        f_print = np.interp(print_area, knots_print, values_print)
        knots_color, values_color = isotonic(color_area, price - mu - f_print)
        f_color = np.interp(color_area, knots_color, values_color)
        if np.abs(f_print - previous).max() < TOLERANCE:
            break
    else:
        raise RuntimeError(f"backfit did not converge in {MAX_ITERATIONS} iterations")
    return mu, knots_print, values_print, knots_color, values_color


def _round6(values):
    return [round(float(v), 6) for v in values]


def fit(rows):
    if not rows:
        raise ValueError("cannot fit an empty dataset")
    color = np.array([float(r["color_area"]) for r in rows])
    bw = np.array([float(r["bw_area"]) for r in rows])
    price = np.array([float(r["price"]) for r in rows])
    mu, kp, vp, kc, vc = fit_additive(color + bw, color, price)
    return {
        "intercept": mu,
        "print_thresholds": _round6(kp),
        "print_values": _round6(vp),
        "color_thresholds": _round6(kc),
        "color_values": _round6(vc),
    }


def evaluate(model, rows, config):
    from pricing import page_price

    errors = []
    for r in rows:
        color_cov = float(r["color_area"]) / 100.0
        bw_cov = float(r["bw_area"]) / 100.0
        predicted = page_price(model, color_cov, bw_cov, config)
        errors.append(abs(predicted - float(r["price"])))
    arr = np.array(errors) if errors else np.array([0.0])
    return {
        "n_rows": len(rows),
        "mean_abs_error": float(arr.mean()),
        "max_abs_error": float(arr.max()),
        "p95_abs_error": float(np.percentile(arr, 95)),
    }
