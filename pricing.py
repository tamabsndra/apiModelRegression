from config import Config


def ladder_round(price, step):
    if step <= 0:
        return int(price)
    return ((int(price) + step - 1) // step) * step

def calculate_price(color_coverage, bw_coverage, config=None):
    if config is None:
        config = Config()

    color_raw = config.PRICE_COEFF_COLOR * (color_coverage * 100) + config.PRICE_INTERCEPT
    bw_raw = config.PRICE_COEFF_BW * (bw_coverage * 100) + config.PRICE_INTERCEPT

    bw_price = max(int(bw_raw), config.PRICE_FLOOR_BW)
    color_price = max(int(color_raw), config.PRICE_FLOOR_COLOR)

    bw_price = ladder_round(bw_price, config.PRICE_STEP)
    color_price = ladder_round(color_price, config.PRICE_STEP)

    if config.PRICE_CAP is not None:
        bw_price = min(bw_price, config.PRICE_CAP)
        color_price = min(color_price, config.PRICE_CAP)

    total_price = bw_price + color_price
    if config.PRICE_CAP is not None:
        total_price = min(total_price, config.PRICE_CAP)

    return {
        "price": total_price,
        "bw_price": bw_price,
        "color_price": color_price,
    }
