import os
import sys
from io import BytesIO

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def patch_config():
    from config import Config
    original_api_key = Config.API_KEY
    Config.API_KEY = "test-key"
    yield
    Config.API_KEY = original_api_key


@pytest.fixture
def app(patch_config):
    from app import create_app

    app = create_app()
    app.config["UPLOAD_FOLDER"] = "/tmp/test_uploads"
    app.config["TESTING"] = True
    os.makedirs("/tmp/test_uploads", exist_ok=True)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header():
    return {"api-key": "test-key"}


def make_solid_pdf(r, g, b, pages=1):
    """Create a synthetic PDF with solid-color pages."""
    buf = BytesIO()
    images = []
    for _ in range(pages):
        img = Image.new("RGB", (100, 100), (r, g, b))
        images.append(img)
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    buf.seek(0)
    return buf


@pytest.fixture
def bw_pdf():
    return make_solid_pdf(128, 128, 128)


@pytest.fixture
def color_pdf():
    return make_solid_pdf(255, 0, 0)


@pytest.fixture
def mixed_pdf():
    return make_solid_pdf(100, 200, 50)
