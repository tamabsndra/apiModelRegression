import numpy as np


def classify_pixels(pixels):
    r, g, b = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
    is_mono = (r == g) & (g == b)
    bw_count = int(is_mono.sum())
    color_count = int((~is_mono).sum())
    total = color_count + bw_count
    if total == 0:
        return 0.0, 0.0
    color_pct = (color_count / total) * 100
    bw_pct = (bw_count / total) * 100
    return color_pct, bw_pct


def analyze_page(pil_image):
    pixels = np.array(pil_image.convert("RGB"))
    color_cov, bw_cov = classify_pixels(pixels)
    return color_cov / 100, bw_cov / 100
