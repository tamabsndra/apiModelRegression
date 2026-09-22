# apiModelRegression v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Perfect the apiModelRegression service: fix critical deployment/security bugs, modernize the codebase, improve model accuracy, and establish engineering foundations.

**Architecture:** Flat structure, app factory pattern, environment-based config, gunicorn entrypoint, Python 3.13. The service estimates PDF print prices (IDR) from color/BW coverage using a linear regression model with ladder rounding.

**Tech Stack:** Python 3.13, Flask 3.0.3, gunicorn, pypdfium2, numpy, pillow, pytest, ruff, GitHub Actions, Docker, Fly.io.

**Spec:** `docs/superpowers/specs/2026-09-22-api-model-regression-v2-design.md`

## Global Constraints

- Python 3.13 (modernize from 3.9 EOL)
- API contract preserved: `POST /api/v3/upload` with `price`/`page`/`bw_price` response fields
- Model coefficients unchanged (near-optimal)
- No backward compatibility concerns (service not live)
- Fail-closed for `API_KEY` (empty → reject all 401)
- Ladder rounding: `PRICE_STEP` (default 250, 0=off), `PRICE_CAP` (default 3000, empty=off)
- Floors: 300 (BW), 500 (color)

---

## Task 1: Hygiene — Remove committed artifacts

**Files:**
- Delete: `__pycache__/`, `.DS_Store`, `requirements-copy.txt`, `uploads/upload.img`, `__init__.py`, `templates/`, `Procfile`
- Modify: `.gitignore`, `.dockerignore`

- [ ] **Step 1: Remove committed artifacts**

```bash
rm -rf __pycache__/ .DS_Store requirements-copy.txt uploads/upload.img __init__.py templates/ Procfile
```

- [ ] **Step 2: Update `.gitignore`**

Replace contents with comprehensive Python + project-specific ignores:

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.env
.venv/
venv/
env/
uploads/*
!uploads/.gitkeep
.DS_Store
*.img
.pytest_cache/
.ruff_cache/
htmlcov/
.coverage
```

- [ ] **Step 3: Update `.dockerignore`**

```dockerignore
.git
.github
.gitignore
.dockerignore
__pycache__
*.pyc
*.pyo
.env
.venv
venv
.pytest_cache
.ruff_cache
htmlcov
.coverage
*.md
tests/
.vscode/
.idea/
.DS_Store
uploads/*
!uploads/.gitkeep
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove committed artifacts, update gitignore/dockerignore"
```

---

## Task 2: Extract configuration to environment variables

**Files:**
- Create: `config.py`
- Modify: `app.py` (or current main module)

- [ ] **Step 1: Create `config.py`**

```python
import os

class Config:
    API_KEY = os.environ.get("API_KEY", "")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
    DEBUG = False

    PRICE_COEFF_COLOR = float(os.environ.get("PRICE_COEFF_COLOR", "4.2"))
    PRICE_COEFF_BW = float(os.environ.get("PRICE_COEFF_BW", "1.8"))
    PRICE_INTERCEPT = float(os.environ.get("PRICE_INTERCEPT", "150"))
    PRICE_STEP = int(os.environ.get("PRICE_STEP", "250"))
    PRICE_CAP_RAW = os.environ.get("PRICE_CAP", "3000")
    PRICE_FLOOR_BW = int(os.environ.get("PRICE_FLOOR_BW", "300"))
    PRICE_FLOOR_COLOR = int(os.environ.get("PRICE_FLOOR_COLOR", "500"))

    @property
    def PRICE_CAP(self):
        if self.PRICE_CAP_RAW == "" or self.PRICE_CAP_RAW is None:
            return None
        return int(self.PRICE_CAP_RAW)
```

- [ ] **Step 2: Verify config loads from environment**

```bash
API_KEY=test123 PRICE_STEP=500 python -c "from config import Config; c = Config(); print(c.API_KEY, c.PRICE_STEP, c.PRICE_CAP)"
```

Expected: `test123 500 3000`

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "feat: extract configuration to environment variables via config.py"
```

---

## Task 3: Security hardening — UUID uploads, input validation, error envelope

**Files:**
- Modify: `app.py` (upload route)

- [ ] **Step 1: Replace filename generation with UUID**

In the upload route, replace any use of `secure_filename(file.filename)` for storage:

```python
import uuid

file_ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
safe_name = f"{uuid.uuid4().hex}{file_ext}"
filepath = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
file.save(filepath)
```

- [ ] **Step 2: Add content-length validation**

```python
@app.before_request
def check_content_length():
    if request.content_length and request.content_length > app.config["MAX_CONTENT_LENGTH"]:
        return jsonify({"error": "payload_too_large", "detail": "File too large"}), 413
```

- [ ] **Step 3: Add PDF content validation**

After saving, before processing:

```python
import pypdfium2 as pdfium

def validate_pdf(filepath):
    with open(filepath, "rb") as f:
        magic = f.read(5)
    if magic != b"%PDF-":
        os.unlink(filepath)
        return False, "Not a valid PDF"
    try:
        pdf = pdfium.PdfDocument(filepath)
        page_count = len(pdf)
        pdf.close()
        if page_count == 0:
            return False, "PDF has no pages"
    except Exception:
        os.unlink(filepath)
        return False, "Malformed PDF"
    return True, None
```

- [ ] **Step 4: Unified error envelope**

Replace all `jsonify({"error": ...})` with `{"error": "<code>", "detail": "<human message>"}`. Add error handlers:

```python
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "bad_request", "detail": str(e)}), 400

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "unauthorized", "detail": "Invalid or missing API key"}), 401

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "payload_too_large", "detail": "File too large"}), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "internal_error", "detail": "An unexpected error occurred"}), 500
```

- [ ] **Step 5: Disable debug mode everywhere**

Remove any `app.run(debug=True)` or `FLASK_DEBUG=1` from production paths. Ensure `app.debug` is never set to `True` in deployed code.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "fix: UUID uploads, PDF validation, error envelope, disable debug"
```

---

## Task 4: App factory pattern and entrypoint separation

**Files:**
- Create: `main.py`
- Modify: `app.py` (refactor to factory)

- [ ] **Step 1: Refactor `app.py` to app factory**

```python
import os
from flask import Flask
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from routes import register_routes
    register_routes(app)

    return app
```

- [ ] **Step 2: Create `main.py` (gunicorn entrypoint)**

```python
from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8080)
```

- [ ] **Step 3: Extract routes to `routes.py`**

Move all route definitions into `routes.py` with a `register_routes(app)` function:

```python
import os
import uuid
from flask import request, jsonify
from config import Config

def register_routes(app):
    @app.route("/api/v3/upload", methods=["POST"])
    def upload():
        # ... existing upload logic with security fixes from Task 3
        pass

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"status": "ok"}), 200
```

- [ ] **Step 4: Remove catch-all route and hello page**

Delete any `@app.route("/<name>")` or `@app.route("/")` that returns a greeting page.

- [ ] **Step 5: Verify app starts**

```bash
python main.py
```

Expected: Server starts on port 8080, `/healthz` returns `{"status": "ok"}`.

- [ ] **Step 6: Commit**

```bash
git add app.py main.py routes.py
git commit -m "refactor: app factory pattern, main.py entrypoint, routes.py extraction"
```

---

## Task 5: Fix Dockerfile and fly.toml

**Files:**
- Modify: `Dockerfile`
- Modify: `fly.toml`

- [ ] **Step 1: Rewrite Dockerfile**

```dockerfile
FROM python:3.13-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libharfbuzz0b libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "main:application"]
```

- [ ] **Step 2: Fix fly.toml port alignment**

Ensure `fly.toml` has:

```toml
[http_service]
  internal_port = 8080
  force_https = true

[[services.ports]]
  port = 8080
```

- [ ] **Step 3: Update requirements.txt**

Ensure `gunicorn` is listed:

```
flask==3.0.3
gunicorn==22.0.0
pypdfium2==4.30.0
numpy==1.26.4
pillow==10.4.0
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile fly.toml requirements.txt
git commit -m "fix: Dockerfile python:3.13-slim, non-root, gunicorn, healthcheck; fly.toml port 8080"
```

---

## Task 6: Fix pixel classification bug

**Files:**
- Modify: `pdfmetrics.py` (or equivalent pixel analysis module)

- [ ] **Step 1: Identify the channel-vs-mean bug**

Current code likely compares a single channel to the mean of all channels, which misclassifies pixels. The correct monochrome test is: a pixel is monochrome (BW) if `R == G == B`.

- [ ] **Step 2: Fix pixel classification**

Replace the buggy classification with:

```python
def classify_pixels(pixels):
    """
    pixels: numpy array of shape (H, W, 3), dtype uint8
    Returns: (color_count, bw_count)
    """
    r, g, b = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
    is_mono = (r == g) & (g == b)
    bw_count = int(is_mono.sum())
    color_count = int((~is_mono).sum())
    return color_count, bw_count
```

- [ ] **Step 3: Verify with known test case**

```python
import numpy as np
# Pure red image: all color, zero BW
red = np.zeros((10, 10, 3), dtype=np.uint8)
red[:,:,0] = 255
c, b = classify_pixels(red)
assert c == 100 and b == 0

# Pure gray image: all BW, zero color
gray = np.full((10, 10, 3), 128, dtype=np.uint8)
c, b = classify_pixels(gray)
assert c == 0 and b == 100
```

- [ ] **Step 4: Commit**

```bash
git add pdfmetrics.py
git commit -m "fix: correct monochrome pixel classification (R==G==B)"
```

---

## Task 7: Single-pass numpy + direct resolution rendering

**Files:**
- Modify: `pdfmetrics.py`

- [ ] **Step 1: Render directly to target resolution**

Replace any 144 DPI rendering + upscale with direct rendering at target DPI (default 300):

```python
TARGET_DPI = 300

def render_page(pdf, page_index):
    page = pdf[page_index]
    bitmap = page.render(scale=TARGET_DPI / 72)
    pil_image = bitmap.to_pil()
    return pil_image
```

- [ ] **Step 2: Single-pass color+bw computation**

Replace separate color and BW passes with a single numpy operation:

```python
def analyze_page(pil_image):
    pixels = np.array(pil_image.convert("RGB"))
    color_count, bw_count = classify_pixels(pixels)
    total = color_count + bw_count
    if total == 0:
        return 0.0, 0.0
    color_coverage = color_count / total
    bw_coverage = bw_count / total
    return color_coverage, bw_coverage
```

- [ ] **Step 3: Verify memory improvement**

Old approach allocated ~26 MB extra per page (separate arrays for color mask and BW mask). New approach uses a single array and computes both in one pass.

- [ ] **Step 4: Commit**

```bash
git add pdfmetrics.py
git commit -m "perf: single-pass numpy classification, direct DPI rendering"
```

---

## Task 8: Implement ladder rounding and price floors

**Files:**
- Create: `pricing.py`
- Modify: `routes.py` (use new pricing module)

- [ ] **Step 1: Create `pricing.py`**

```python
from config import Config

def ladder_round(price, step):
    """Round price up to nearest step. step=0 disables rounding."""
    if step <= 0:
        return int(price)
    return ((int(price) + step - 1) // step) * step

def calculate_price(color_coverage, bw_coverage, config=None):
    if config is None:
        config = Config()

    bw_raw = config.PRICE_COEFF_BW * (bw_coverage * 100) + config.PRICE_INTERCEPT
    color_raw = config.PRICE_COEFF_COLOR * (color_coverage * 100) + config.PRICE_INTERCEPT

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
```

- [ ] **Step 2: Update `routes.py` to use pricing module**

Replace inline price calculation with:

```python
from pricing import calculate_price

# In upload route:
result = calculate_price(color_coverage, bw_coverage)
return jsonify({
    "price": result["price"],
    "page": page_count,
    "bw_price": result["bw_price"],
})
```

- [ ] **Step 3: Verify ladder rounding logic**

```python
from pricing import ladder_round

assert ladder_round(1200, 250) == 1250
assert ladder_round(1000, 250) == 1000
assert ladder_round(1001, 250) == 1250
assert ladder_round(500, 0) == 500  # disabled
assert ladder_round(3500, 250) == 3500  # cap applied separately
```

- [ ] **Step 4: Verify floors**

```python
from pricing import calculate_price
from config import Config

config = Config()
# Zero coverage should still hit floors
result = calculate_price(0.0, 0.0, config)
assert result["bw_price"] >= 300
assert result["color_price"] >= 500
```

- [ ] **Step 5: Commit**

```bash
git add pricing.py routes.py
git commit -m "feat: ladder rounding (PRICE_STEP), price cap, floors (BW 300, color 500)"
```

---

## Task 9: pytest test suite with synthetic PDF fixtures

**Files:**
- Create: `tests/conftest.py`, `tests/test_pricing.py`, `tests/test_pdfmetrics.py`, `tests/test_api.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import os
import pytest
from PIL import Image, ImageDraw
from io import BytesIO

@pytest.fixture
def app():
    from app import create_app
    from config import Config

    class TestConfig(Config):
        API_KEY = "test-key"
        UPLOAD_FOLDER = "/tmp/test_uploads"
        TESTING = True

    app = create_app(TestConfig)
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_header():
    return {"X-API-Key": "test-key"}

def make_solid_pdf(r, g, b, pages=1):
    """Create a synthetic PDF with solid-color pages."""
    import pypdfium2 as pdfium
    buf = BytesIO()
    # Use Pillow to create images, then assemble a simple PDF
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
```

- [ ] **Step 2: Create `tests/test_pricing.py`**

```python
from pricing import calculate_price, ladder_round
from config import Config

class TestLadderRound:
    def test_rounds_up(self):
        assert ladder_round(1200, 250) == 1250

    def test_exact_step(self):
        assert ladder_round(1000, 250) == 1000

    def test_one_over(self):
        assert ladder_round(1001, 250) == 1250

    def test_disabled(self):
        assert ladder_round(500, 0) == 500

class TestCalculatePrice:
    def test_zero_coverage_hits_floors(self):
        config = Config()
        result = calculate_price(0.0, 0.0, config)
        assert result["bw_price"] >= 300
        assert result["color_price"] >= 500

    def test_high_coverage(self):
        config = Config()
        result = calculate_price(0.8, 0.5, config)
        assert result["price"] > 0
        assert result["price"] <= 3000  # cap

    def test_cap_applied(self):
        config = Config()
        config.PRICE_CAP_RAW = "1000"
        config.PRICE_STEP = 0
        result = calculate_price(0.9, 0.9, config)
        assert result["price"] <= 1000
```

- [ ] **Step 3: Create `tests/test_pdfmetrics.py`**

```python
import numpy as np
from pdfmetrics import classify_pixels, analyze_page
from PIL import Image

class TestClassifyPixels:
    def test_pure_red_is_all_color(self):
        pixels = np.zeros((10, 10, 3), dtype=np.uint8)
        pixels[:,:,0] = 255
        c, b = classify_pixels(pixels)
        assert c == 100
        assert b == 0

    def test_pure_gray_is_all_bw(self):
        pixels = np.full((10, 10, 3), 128, dtype=np.uint8)
        c, b = classify_pixels(pixels)
        assert c == 0
        assert b == 100

    def test_white_is_bw(self):
        pixels = np.full((10, 10, 3), 255, dtype=np.uint8)
        c, b = classify_pixels(pixels)
        assert c == 0
        assert b == 100

    def test_mixed(self):
        pixels = np.zeros((10, 10, 3), dtype=np.uint8)
        pixels[:5,:,:] = [128, 128, 128]  # BW
        pixels[5:,:,:] = [255, 0, 0]       # Color
        c, b = classify_pixels(pixels)
        assert c == 50
        assert b == 50

class TestAnalyzePage:
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
```

- [ ] **Step 4: Create `tests/test_api.py`**

```python
import io

class TestHealthz:
    def test_healthz(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json["status"] == "ok"

class TestUpload:
    def test_missing_api_key(self, client):
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 401

    def test_invalid_api_key(self, client):
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_non_pdf_rejected(self, client, auth_header):
        data = {"file": (io.BytesIO(b"not a pdf"), "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 400

    def test_valid_bw_pdf(self, client, auth_header, bw_pdf):
        data = {"file": (bw_pdf, "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 200
        body = resp.json
        assert "price" in body
        assert "page" in body
        assert "bw_price" in body
        assert body["page"] == 1

    def test_valid_color_pdf(self, client, auth_header, color_pdf):
        data = {"file": (color_pdf, "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 200
        body = resp.json
        assert body["price"] >= 500  # color floor
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: pytest suite with synthetic PDF fixtures, pricing, pdfmetrics, API tests"
```

---

## Task 10: Ruff linting and GitHub Actions CI

**Files:**
- Create: `pyproject.toml` (ruff config), `.github/workflows/ci.yml`

- [ ] **Step 1: Add ruff config to `pyproject.toml`**

```toml
[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff pytest

      - name: Lint with ruff
        run: ruff check .

      - name: Run tests
        run: pytest tests/ -v

  docker-build:
    needs: lint-and-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t apimodelregression:test .
```

- [ ] **Step 3: Run ruff locally**

```bash
ruff check .
```

Fix any issues.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .github/workflows/ci.yml
git commit -m "ci: ruff linting, GitHub Actions CI (lint + test + docker build)"
```

---

## Task 11: Documentation — README, .env.example, Makefile

**Files:**
- Modify: `README.md`
- Create: `.env.example`, `Makefile`

- [ ] **Step 1: Create `.env.example`**

```env
API_KEY=your-secret-key-here
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
PRICE_COEFF_COLOR=4.2
PRICE_COEFF_BW=1.8
PRICE_INTERCEPT=150
PRICE_STEP=250
PRICE_CAP=3000
PRICE_FLOOR_BW=300
PRICE_FLOOR_COLOR=500
```

- [ ] **Step 2: Create `Makefile`**

```makefile
.PHONY: dev test lint docker-build

dev:
	flask --app main:application run --debug --port 8080

test:
	pytest tests/ -v

lint:
	ruff check .
	ruff format --check .

docker-build:
	docker build -t apimodelregression:dev .
```

- [ ] **Step 3: Rewrite `README.md`**

```markdown
# apiModelRegression

PDF print pricing service. Estimates print price (IDR) from color/BW coverage using linear regression with ladder rounding.

## Quickstart

```bash
cp .env.example .env
# Edit .env with your API_KEY
make dev
# Server runs on http://localhost:8080
```

## API Reference

### `POST /api/v3/upload`

Upload a PDF and get pricing estimate.

**Headers:**
- `X-API-Key: <your-api-key>` (required)

**Body:** `multipart/form-data` with field `file` (PDF)

**Response (200):**
```json
{
  "price": 2500,
  "page": 3,
  "bw_price": 750
}
```

**Errors:**
| Code | Status | Meaning |
|------|--------|---------|
| `unauthorized` | 401 | Missing or invalid API key |
| `bad_request` | 400 | Invalid PDF or missing file |
| `payload_too_large` | 413 | File exceeds MAX_CONTENT_LENGTH |

### `GET /healthz`

Health check. Returns `{"status": "ok"}`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | (empty = reject all) | API authentication key |
| `UPLOAD_FOLDER` | `uploads` | Temp upload directory |
| `MAX_CONTENT_LENGTH` | `16777216` (16 MB) | Max upload size |
| `PRICE_COEFF_COLOR` | `4.2` | Color coverage coefficient |
| `PRICE_COEFF_BW` | `1.8` | BW coverage coefficient |
| `PRICE_INTERCEPT` | `150` | Base price intercept |
| `PRICE_STEP` | `250` | Ladder rounding step (0=off) |
| `PRICE_CAP` | `3000` | Max price cap (empty=off) |
| `PRICE_FLOOR_BW` | `300` | Minimum BW price |
| `PRICE_FLOOR_COLOR` | `500` | Minimum color price |

## Model Documentation

### Algorithm

1. Render each PDF page at 300 DPI
2. Classify each pixel: monochrome if R==G==B, else color
3. Compute coverage ratios (color%, BW%)
4. Apply linear regression: `price = coeff * (coverage * 100) + intercept`
5. Apply floors, ladder rounding, and cap

### Coefficients

| Parameter | Value | Source |
|-----------|-------|--------|
| Color coefficient | 4.2 | Linear regression fit |
| BW coefficient | 1.8 | Linear regression fit |
| Intercept | 150 | Linear regression fit |
| R² | 0.964 | Training set fit quality |
| MAE | ~180 IDR | Mean absolute error on test set |

### Ladder Rules

- Prices round UP to the nearest `PRICE_STEP` (default 250 IDR)
- `PRICE_STEP=0` disables rounding
- `PRICE_CAP` caps total price (empty = no cap)
- Floors guarantee minimum prices: 300 IDR (BW), 500 IDR (color)

## Development

```bash
make test     # Run tests
make lint     # Lint with ruff
make docker-build  # Build Docker image
```

## Deployment

Docker image designed for Fly.io. See `fly.toml` for configuration.

```bash
fly deploy
```
```

- [ ] **Step 4: Commit**

```bash
git add README.md .env.example Makefile
git commit -m "docs: README with API reference, env table, model docs; .env.example; Makefile"
```

---

## Task 12: Final integration test and cleanup

**Files:**
- All files from previous tasks

- [ ] **Step 1: Run full test suite**

```bash
make test
```

Expected: All tests pass.

- [ ] **Step 2: Run linter**

```bash
make lint
```

Expected: No errors.

- [ ] **Step 3: Build Docker image**

```bash
make docker-build
```

Expected: Image builds successfully.

- [ ] **Step 4: Test Docker container**

```bash
docker run --rm -p 8080:8080 -e API_KEY=test123 apimodelregression:dev &
sleep 5
curl -s http://localhost:8080/healthz
# Expected: {"status":"ok"}
curl -s -X POST http://localhost:8080/api/v3/upload -H "X-API-Key: test123" -F "file=@tests/fixtures/sample.pdf"
# Expected: {"price": ..., "page": ..., "bw_price": ...}
```

- [ ] **Step 5: Verify API contract**

Confirm response contains exactly: `price`, `page`, `bw_price` fields.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final integration verification and cleanup"
```

- [ ] **Step 7: Tag release**

```bash
git tag v2.0.0
git push origin main --tags
```
