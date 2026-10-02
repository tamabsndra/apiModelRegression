import numpy as np
import pypdfium2 as pdfium

from config import Config
from model_store import get_active_model
from pricing import calculate_price
from pricing_model import latent_price

TARGET_DPI = 300


def classify_pixels(pixels):
    r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    is_mono = (r == g) & (g == b)
    is_white = (r == 255) & (g == 255) & (b == 255)
    color_count = int((~is_mono).sum())
    bw_count = int((is_mono & ~is_white).sum())
    return color_count, bw_count


def analyze_page(pil_image):
    pixels = np.array(pil_image.convert("RGB"))
    color_count, bw_count = classify_pixels(pixels)
    total = pixels.shape[0] * pixels.shape[1]
    if total == 0:
        return 0.0, 0.0
    color_coverage = color_count / total
    bw_coverage = bw_count / total
    return color_coverage, bw_coverage


def render_page(pdf, page_index):
    page = pdf[page_index]
    bitmap = page.render(scale=TARGET_DPI / 72)
    return bitmap.to_pil()


def getprice(pdf_path):
    return int(sum(page["price"] for page in getprice_detail(pdf_path)))


def getprice_detail(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    config = Config()
    model = get_active_model()
    details = []
    for i in range(len(pdf)):
        pil_image = render_page(pdf, i)
        color_cov, bw_cov = analyze_page(pil_image)
        print_pct = (color_cov + bw_cov) * 100
        color_pct = color_cov * 100
        pricing = calculate_price(color_cov, bw_cov, config, model=model)
        details.append(
            {
                "index": i + 1,
                "print_pct": round(print_pct, 4),
                "color_pct": round(color_pct, 4),
                "bw_pct": round(bw_cov * 100, 4),
                "latent": round(float(latent_price(model, print_pct, color_pct)), 2),
                "bw_price": pricing["bw_price"],
                "color_price": pricing["color_price"],
                "price": pricing["price"],
            }
        )
    return details


def getpage(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    return len(pdf)
