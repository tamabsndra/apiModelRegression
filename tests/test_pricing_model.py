import numpy as np

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
