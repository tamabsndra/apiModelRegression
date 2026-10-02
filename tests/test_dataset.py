import csv
from pathlib import Path

import numpy as np

import model_store
from config import Config
from pricing import calculate_price
from pricing_model import latent_price


def _model():
    return model_store.baked_model()


DATASET_PATH = Path(__file__).resolve().parent.parent / "new-dataset.csv"

# Fitted model scores, measured with 10-fold CV and reproduced in-sample here.
# Guards against silent regression to the old linear form (MAE ~107, R2 ~0.953).
MAX_MAE = 55.0
MIN_R2 = 0.97


def load_dataset():
    rows = list(csv.DictReader(DATASET_PATH.open()))
    assert rows, "dataset must not be empty"
    color = np.array([float(r["color_area"]) for r in rows])
    bw = np.array([float(r["bw_area"]) for r in rows])
    price = np.array([float(r["price"]) for r in rows])
    return color, bw, color + bw, price


def test_dataset_fit_quality():
    model = _model()
    config = Config()
    config.PRICE_STEP = 250
    config.PRICE_CAP_RAW = "3000"

    color, bw, print_area, actual = load_dataset()
    predicted = np.array(
        [
            calculate_price(c / 100, b / 100, config, model=model)["price"]
            for c, b in zip(color, bw, strict=True)
        ]
    )

    mae = float(np.abs(predicted - actual).mean())
    ss_res = float(((predicted - actual) ** 2).sum())
    ss_tot = float(((actual - actual.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot

    assert mae <= MAX_MAE, f"MAE {mae:.2f} exceeds {MAX_MAE}"
    assert r2 >= MIN_R2, f"R2 {r2:.4f} below {MIN_R2}"


# Latent error is higher than laddered error because the labels already sit on
# the 250 grid, which the ladder snap can hit exactly. The old linear form
# scored 122.3 here, so this threshold still catches a regression to it.
MAX_LATENT_MAE = 70.0


def test_latent_price_tracks_dataset():
    """Latent (pre-ladder) model must track the dataset closely on its own."""
    model = _model()
    color, _, print_area, actual = load_dataset()
    latent = np.array([latent_price(model, p, c) for p, c in zip(print_area, color, strict=True)])
    mae = float(np.abs(latent - actual).mean())
    assert mae <= MAX_LATENT_MAE, f"latent MAE {mae:.2f} exceeds {MAX_LATENT_MAE}"
