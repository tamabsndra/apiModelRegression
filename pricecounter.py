
import numpy as np
import pypdfium2 as pdfium

TARGET_DPI = 300

def classify_pixels(pixels):
    r, g, b = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
    is_mono = (r == g) & (g == b)
    bw_count = int(is_mono.sum())
    color_count = int((~is_mono).sum())
    return color_count, bw_count

def analyze_page(pil_image):
    pixels = np.array(pil_image.convert("RGB"))
    color_count, bw_count = classify_pixels(pixels)
    total = color_count + bw_count
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
    total_color_coverage = 0.0
    total_bw_coverage = 0.0
    for i in range(len(pdf)):
        pil_image = render_page(pdf, i)
        color_cov, bw_cov = analyze_page(pil_image)
        total_color_coverage += color_cov
        total_bw_coverage += bw_cov
    avg_color_coverage = total_color_coverage / len(pdf) if len(pdf) > 0 else 0.0
    avg_bw_coverage = total_bw_coverage / len(pdf) if len(pdf) > 0 else 0.0
    from config import Config
    from pricing import calculate_price
    config = Config()
    result = calculate_price(avg_color_coverage, avg_bw_coverage, config)
    return result["price"]

def getpage(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    return len(pdf)
