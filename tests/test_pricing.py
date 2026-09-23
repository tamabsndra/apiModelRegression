from config import Config
from pricing import calculate_price, ladder_round


def make_config(step=250, cap="3000"):
    config = Config()
    config.PRICE_STEP = step
    config.PRICE_CAP_RAW = cap
    return config


class TestLadderRound:
    def test_nearest_down(self):
        assert ladder_round(304, 250) == 250

    def test_nearest_up(self):
        assert ladder_round(1200, 250) == 1250

    def test_exact_step(self):
        assert ladder_round(1000, 250) == 1000

    def test_disabled(self):
        assert ladder_round(544.04, 0) == 544


class TestCalculatePrice:
    def test_blank_page_floors_to_300(self):
        result = calculate_price(0.0, 0.0, make_config())
        assert result["price"] == 300
        assert result["bw_price"] == 300
        assert result["color_price"] == 0

    def test_default_config_blank_page(self):
        assert calculate_price(0.0, 0.0)["price"] == 300

    def test_light_bw_stays_at_floor(self):
        result = calculate_price(0.0, 0.10, make_config())
        assert result["price"] == 300

    def test_mid_bw_snaps_to_500(self):
        result = calculate_price(0.0, 0.50, make_config())
        assert result["price"] == 500
        assert result["bw_price"] == 500
        assert result["color_price"] == 0

    def test_mixed_page(self):
        result = calculate_price(0.10, 0.90, make_config())
        assert result["price"] == 1000
        assert result["bw_price"] == 750
        assert result["color_price"] == 250

    def test_full_color_page(self):
        result = calculate_price(1.0, 0.0, make_config())
        assert result["price"] == 2750
        assert result["bw_price"] == 300
        assert result["color_price"] == 2450

    def test_cap_applied(self):
        result = calculate_price(1.0, 0.0, make_config(cap="1000"))
        assert result["price"] == 1000

    def test_empty_price_cap_disables_cap(self, monkeypatch):
        monkeypatch.setattr(Config, "PRICE_CAP_RAW", "")
        config = Config()
        assert config.PRICE_CAP is None
        assert calculate_price(1.0, 0.0, config)["price"] > 2500

    def test_tiny_color_coverage_hits_color_floor(self):
        result = calculate_price(0.0001, 0.0, make_config())
        assert result["price"] == 500

    def test_step_disabled(self):
        result = calculate_price(0.0, 0.50, make_config(step=0))
        assert result["price"] == 544

    def test_decomposition_sums_to_price(self):
        for color, bw in [(0.0, 0.0), (0.0, 0.5), (0.1, 0.9), (1.0, 0.0), (0.4, 0.3)]:
            result = calculate_price(color, bw, make_config())
            assert result["bw_price"] + result["color_price"] == result["price"]

    def test_floor_never_broken_by_snap(self):
        for bw in [0.0, 0.01, 0.05, 0.10, 0.15]:
            result = calculate_price(0.0, bw, make_config())
            assert result["price"] >= 300
