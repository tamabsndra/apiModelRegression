import numpy as np
import pypdfium2 as pdfium

from config import Config
from pricing import calculate_price

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
    pdf = pdfium.PdfDocument(pdf_path)
    config = Config()
    total_price = 0
    for i in range(len(pdf)):
        pil_image = render_page(pdf, i)
        color_cov, bw_cov = analyze_page(pil_image)
        total_price += calculate_price(color_cov, bw_cov, config)["price"]
    return int(total_price)


def getpage(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    return len(pdf)
