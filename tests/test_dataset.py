import csv
from pathlib import Path

from config import Config
from pricing import calculate_price

DATASET_PATH = Path(__file__).resolve().parent.parent / "new-dataset.csv"


def test_dataset_regression():
    config = Config()
    config.PRICE_STEP = 250
    config.PRICE_CAP_RAW = "3000"

    rows = list(csv.DictReader(DATASET_PATH.open()))
    assert rows, "dataset must not be empty"

    preds = [
        calculate_price(float(r["color_area"]) / 100, float(r["bw_area"]) / 100, config)["price"]
        for r in rows
    ]
    actuals = [float(r["price"]) for r in rows]

    mae = sum(abs(p - a) for p, a in zip(preds, actuals)) / len(actuals)
    mean_actual = sum(actuals) / len(actuals)
    ss_res = sum((p - a) ** 2 for p, a in zip(preds, actuals))
    ss_tot = sum((a - mean_actual) ** 2 for a in actuals)
    r2 = 1 - ss_res / ss_tot

    print(f"\nDataset MAE={mae:.2f} IDR, R2={r2:.4f} (n={len(actuals)})")
    assert mae <= 130, f"MAE {mae:.2f} exceeds 130"
    assert r2 >= 0.90, f"R2 {r2:.4f} below 0.90"
