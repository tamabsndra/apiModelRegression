import pypdfium2 as pdfium
import numpy as np
from concurrent.futures import ProcessPoolExecutor

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

def process_page(page_number, pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_number]
    bitmap = page.render(scale=TARGET_DPI / 72)
    pil_image = bitmap.to_pil()
    color_coverage, bw_coverage = analyze_page(pil_image)
    from pricing import calculate_price
    from config import Config
    config = Config()
    result = calculate_price(color_coverage, bw_coverage, config)
    return result["price"]

def getprice(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_page, i, pdf_path) for i in range(len(pdf))]
        harga_total = sum(future.result() for future in futures)
    return harga_total

def getpage(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    return len(pdf)
