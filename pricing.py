from config import Config


def ladder_round(price, step):
    """Snap price to the nearest multiple of step; step <= 0 disables snapping."""
    if step <= 0:
        return int(price)
    return round(price / step) * step


def _page_price(color_coverage, bw_coverage, config):
    color_pct = color_coverage * 100
    print_pct = (color_coverage + bw_coverage) * 100
    raw = (
        config.PRICE_INTERCEPT
        + config.PRICE_COEFF_COLOR * color_pct
        + config.PRICE_COEFF_BW * print_pct
    )
    floor = config.PRICE_FLOOR_BW if color_pct == 0 else config.PRICE_FLOOR_COLOR
    price = max(ladder_round(max(raw, floor), config.PRICE_STEP), floor)
    if config.PRICE_CAP is not None:
        price = min(price, config.PRICE_CAP)
    return price


def calculate_price(color_coverage, bw_coverage, config=None):
    """Price a single page from coverage fractions (0-1).

    Per-page model (v1 semantics), single intercept counted once:

        raw = PRICE_INTERCEPT
            + PRICE_COEFF_COLOR * color_area_pct
            + PRICE_COEFF_BW * print_area_pct

    where print_area_pct = (color_coverage + bw_coverage) * 100. The floor
    (PRICE_FLOOR_BW when the page has no color, else PRICE_FLOOR_COLOR)
    applies to raw before the ladder snap, and the snapped price is never
    allowed below the floor. PRICE_CAP applies last.

    Returns:
        price: the page price after floor, ladder snap, and cap.
        bw_price: what the page would cost in pure B&W — the page price with
            color_coverage forced to 0.0.
        color_price: max(0, price - bw_price), the color premium over B&W.
    """
    if config is None:
        config = Config()
    page_price = _page_price(color_coverage, bw_coverage, config)
    bw_only_price = _page_price(0.0, bw_coverage, config)
    return {
        "price": page_price,
        "bw_price": bw_only_price,
        "color_price": max(0, page_price - bw_only_price),
    }
