from pricing import calculate_price, ladder_round
from config import Config

class TestLadderRound:
    def test_rounds_up(self):
        assert ladder_round(1200, 250) == 1250

    def test_exact_step(self):
        assert ladder_round(1000, 250) == 1000

    def test_one_over(self):
        assert ladder_round(1001, 250) == 1250

    def test_disabled(self):
        assert ladder_round(500, 0) == 500

class TestCalculatePrice:
    def test_zero_coverage_hits_floors(self):
        config = Config()
        result = calculate_price(0.0, 0.0, config)
        assert result["bw_price"] >= 300
        assert result["color_price"] >= 500

    def test_high_coverage(self):
        config = Config()
        result = calculate_price(0.8, 0.5, config)
        assert result["price"] > 0
        assert result["price"] <= 3000

    def test_cap_applied(self):
        config = Config()
        config.PRICE_CAP_RAW = "1000"
        config.PRICE_STEP = 0
        result = calculate_price(0.9, 0.9, config)
        assert result["price"] <= 1000
