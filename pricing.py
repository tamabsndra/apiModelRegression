from config import Config
from model_store import get_active_model
from pricing_model import latent_price


def ladder_round(price, step):
    if step <= 0:
        return int(price)
    return round(price / step) * step


def page_price(model, color_coverage, bw_coverage, config):
    color_pct = color_coverage * 100
    print_pct = (color_coverage + bw_coverage) * 100
    raw = latent_price(model, print_pct, color_pct)
    floor = config.PRICE_FLOOR_BW if color_pct == 0 else config.PRICE_FLOOR_COLOR
    price = max(ladder_round(max(raw, floor), config.PRICE_STEP), floor)
    if config.PRICE_CAP is not None:
        price = min(price, config.PRICE_CAP)
    return price


def calculate_price(color_coverage, bw_coverage, config=None, model=None):
    if config is None:
        config = Config()
    if model is None:
        model = get_active_model()
    page = page_price(model, color_coverage, bw_coverage, config)
    bw_only = page_price(model, 0.0, bw_coverage, config)
    return {"price": page, "bw_price": bw_only, "color_price": max(0, page - bw_only)}
