import numpy as np
from PIL import Image

from pricecounter import analyze_page, classify_pixels


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
