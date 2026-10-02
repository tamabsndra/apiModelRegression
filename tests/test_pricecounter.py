import io

import numpy as np
import pytest
from PIL import Image

import model_store
from pricecounter import analyze_page, classify_pixels, getprice, getprice_detail


@pytest.fixture(autouse=True)
def reset_store_cache():
    model_store.reset_cache()
    yield


def make_pdf_bytes(r, g, b, pages=1):
    buf = io.BytesIO()
    images = [Image.new("RGB", (100, 100), (r, g, b)) for _ in range(pages)]
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    buf.seek(0)
    return buf.getvalue()


class TestGetpricePerPage:
    def test_blank_three_pages_price_900(self, tmp_path):
        path = tmp_path / "blank3.pdf"
        path.write_bytes(make_pdf_bytes(255, 255, 255, pages=3))
        assert getprice(str(path)) == 900

    def test_ten_gray_pages_proportional_to_single_page(self, tmp_path):
        one = tmp_path / "gray1.pdf"
        ten = tmp_path / "gray10.pdf"
        one.write_bytes(make_pdf_bytes(128, 128, 128, pages=1))
        ten.write_bytes(make_pdf_bytes(128, 128, 128, pages=10))
        assert getprice(str(ten)) == 10 * getprice(str(one))


class TestClassifyPixels:
    def test_pure_red_is_all_color(self):
        pixels = np.zeros((10, 10, 3), dtype=np.uint8)
        pixels[:, :, 0] = 255
        c, b = classify_pixels(pixels)
        assert c == 100
        assert b == 0

    def test_pure_gray_is_all_bw(self):
        pixels = np.full((10, 10, 3), 128, dtype=np.uint8)
        c, b = classify_pixels(pixels)
        assert c == 0
        assert b == 100

    def test_white_is_not_ink(self):
        pixels = np.full((10, 10, 3), 255, dtype=np.uint8)
        c, b = classify_pixels(pixels)
        assert c == 0
        assert b == 0

    def test_mixed(self):
        pixels = np.zeros((10, 10, 3), dtype=np.uint8)
        pixels[:5, :, :] = [128, 128, 128]
        pixels[5:, :, :] = [255, 0, 0]
        c, b = classify_pixels(pixels)
        assert c == 50
        assert b == 50


class TestAnalyzePage:
    def test_blank_page_has_zero_coverage(self):
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        color_cov, bw_cov = analyze_page(img)
        assert color_cov == 0.0
        assert bw_cov == 0.0

    def test_solid_gray(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        color_cov, bw_cov = analyze_page(img)
        assert color_cov == 0.0
        assert abs(bw_cov - 1.0) < 0.01

    def test_solid_red(self):
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        color_cov, bw_cov = analyze_page(img)
        assert abs(color_cov - 1.0) < 0.01
        assert bw_cov == 0.0

    def test_coverage_is_fraction_of_full_page(self):
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        for y in range(10):
            for x in range(100):
                img.putpixel((x, y), (128, 128, 128))
        color_cov, bw_cov = analyze_page(img)
        assert color_cov == 0.0
        assert abs(bw_cov - 0.10) < 0.01


class TestGetpriceDetail:
    def test_returns_list_per_page(self, tmp_path):
        path = tmp_path / "two_bw.pdf"
        path.write_bytes(make_pdf_bytes(128, 128, 128, pages=2))
        result = getprice_detail(str(path))
        assert isinstance(result, list)
        assert len(result) == 2

    def test_each_page_has_required_fields(self, tmp_path):
        path = tmp_path / "one.pdf"
        path.write_bytes(make_pdf_bytes(128, 128, 128, pages=1))
        result = getprice_detail(str(path))
        page = result[0]
        required = {
            "index",
            "print_pct",
            "color_pct",
            "bw_pct",
            "latent",
            "bw_price",
            "color_price",
            "price",
        }
        assert required.issubset(page.keys())

    def test_blank_page_zero_coverage(self, tmp_path):
        path = tmp_path / "blank.pdf"
        path.write_bytes(make_pdf_bytes(255, 255, 255, pages=1))
        result = getprice_detail(str(path))
        assert result[0]["print_pct"] == 0.0
        assert result[0]["color_pct"] == 0.0
        assert result[0]["bw_pct"] == 0.0
        assert result[0]["price"] >= 300

    def test_total_matches_getprice(self, tmp_path):
        path = tmp_path / "multi.pdf"
        path.write_bytes(make_pdf_bytes(200, 50, 100, pages=3))
        detail_total = sum(p["price"] for p in getprice_detail(str(path)))
        assert detail_total == getprice(str(path))

    def test_solid_color_page_has_zero_bw(self, tmp_path):
        path = tmp_path / "color.pdf"
        path.write_bytes(make_pdf_bytes(255, 0, 0, pages=1))
        result = getprice_detail(str(path))
        assert result[0]["bw_pct"] == 0.0
        assert result[0]["color_pct"] > 0.9
        assert result[0]["bw_price"] <= result[0]["price"]
        assert result[0]["color_price"] >= 0
