import numpy as np

from config import Config
from pricing import calculate_price
from pricing_model import latent_price


class TestLatentPriceMonotonicity:
    def test_more_print_area_never_costs_less(self):
        values = [latent_price(p, 0.0) for p in np.arange(0.0, 100.1, 1.0)]
        assert all(b >= a for a, b in zip(values, values[1:])), values

    def test_more_colour_area_never_costs_less(self):
        values = [latent_price(50.0, c) for c in np.arange(0.0, 50.1, 1.0)]
        assert all(b >= a for a, b in zip(values, values[1:])), values


class TestGeneratedArtifact:
    """The shipped artifact must match the dataset it was fitted from."""

    def test_artifact_matches_dataset_hash(self):
        import csv
        import hashlib
        from pathlib import Path

        from pricing_model_data import DATASET_ROWS, DATASET_SHA256

        dataset = Path(__file__).resolve().parent.parent / "new-dataset.csv"
        actual = hashlib.sha256(dataset.read_bytes()).hexdigest()
        assert actual == DATASET_SHA256, (
            "new-dataset.csv changed but pricing_model_data.py was not refit; "
            "run `python3 tools_fit_model.py`"
        )
        assert len(list(csv.DictReader(dataset.open()))) == DATASET_ROWS


# The dataset only contains 73 colourless pages, all between 0.37% and 7.89%
# ink and all at the 300 IDR floor. Anything above that is extrapolation from
# colour-bearing pages, so pin the curve here: if a refit moves these numbers,
# the B&W behaviour changed and the change should be reviewed deliberately.
BW_PRICE_CURVE = [
    (0.00, 300),
    (0.05, 300),
    (0.10, 300),
    (0.19, 300),
    (0.20, 500),
    (0.35, 500),
    (0.36, 750),
    (0.67, 750),
    (0.68, 1000),
    (0.94, 1000),
    (0.95, 1250),
    (1.00, 1250),
]


class TestBwPriceCurve:
    def test_bw_only_curve(self):
        config = Config()
        for coverage, expected in BW_PRICE_CURVE:
            actual = calculate_price(0.0, coverage, config)["price"]
            assert actual == expected, f"bw coverage {coverage}: {actual} != {expected}"

    def test_bw_only_never_exceeds_full_colour_page(self):
        config = Config()
        heaviest_bw = calculate_price(0.0, 1.0, config)["price"]
        full_colour = calculate_price(1.0, 0.0, config)["price"]
        assert heaviest_bw <= full_colour
