# apiModelRegression Backend (Labeling, Training, Model Serving) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Flask service into the labeling UI backend, the training compute endpoint, and the runtime that serves prices from the artivity-server active model (with cache + baked fallback).

**Architecture:** New `artivity_client.py` (stdlib `urllib`) talks to artivity-server; Flask session cookies carry the owner token; labeling routes proxy to artivity-server; `/internal/train` runs the extracted isotonic fit; `model_store.py` pull-through caches the active model with a baked fallback. `pricing.py`/`pricing_model.py` accept a model object.

**Tech Stack:** Python 3.13, Flask 3, numpy, pypdfium2, Pillow, pytest, ruff. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-10-02-print-pricing-labeling-retrain-design.md`

## Global Constraints

- Never break `POST /api/v3/upload` response contract or `/api/v3/config`.
- Outbound HTTP uses stdlib `urllib.request`; tests monkeypatch it. No `requests`.
- Owner gate: session cookie is httpOnly signed; every mutating route requires header `X-Requested-With`.
- `/internal/train` requires `X-API-Key == PRINT_PRICING_SERVICE_TOKEN` (constant-time, fail-closed 503 when unset).
- Rate of lint/test: run `make lint` then `make test` before each commit.
- Existing tests must stay green; `pricing` tests may be updated to inject a model object.

---

### Task 1: Extract the fit/evaluate core (`model_fit.py`)

**Files:**
- Create: `model_fit.py`
- Modify: `tools_fit_model.py`
- Test: `tests/test_model_fit.py`

**Interfaces:**
- Produces: `fit(rows: list[dict]) -> dict`, `evaluate(model: dict, rows: list[dict], config) -> dict`.
- `rows` items have numeric `bw_area`, `color_area`, `price`.
- `fit` returns `{"intercept": float, "print_thresholds": list[float], "print_values": list[float], "color_thresholds": list[float], "color_values": list[float]}`.
- `evaluate` returns `{"n_rows": int, "mean_abs_error": float, "max_abs_error": float, "p95_abs_error": float}` computed on final prices.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_fit.py
import pytest

from model_fit import evaluate, fit


def _rows():
    # Price rises with ink; the fit must be monotone and coherent.
    rows = []
    for i in range(1, 21):
        color = i * 4.0
        rows.append({"bw_area": 1.0, "color_area": color, "price": float(500 + i * 100)})
    return rows


def test_fit_is_monotone_and_evaluate_reports_zero_error_on_exact_fit():
    rows = _rows()
    model = fit(rows)
    assert model["print_thresholds"] == sorted(model["print_thresholds"])
    assert model["color_thresholds"] == sorted(model["color_thresholds"])

    class Cfg:
        PRICE_STEP = 250
        PRICE_FLOOR_BW = 300
        PRICE_FLOOR_COLOR = 500
        PRICE_CAP = None

    metrics = evaluate(model, rows, Cfg)
    assert metrics["n_rows"] == len(rows)
    # The fitted model reproduces the ladder-rounded labels for monotone data.
    assert metrics["mean_abs_error"] <= 250


def test_fit_rejects_empty_rows():
    with pytest.raises(ValueError):
        fit([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model_fit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'model_fit'`.

- [ ] **Step 3: Create `model_fit.py` (move the numpy core out of tools_fit_model.py)**

```python
"""Pure additive isotonic fitting and evaluation for print pricing.

Both f_print and f_color are monotone non-decreasing step functions:
    latent = INTERCEPT + f_print(print_area) + f_color(color_area)
"""

import numpy as np

TOLERANCE = 1e-9
MAX_ITERATIONS = 5000


def pava(y, w):
    values, weights, counts = [], [], []
    for value, weight in zip(y, w, strict=True):
        values.append(float(value))
        weights.append(float(weight))
        counts.append(1)
        while len(values) > 1 and values[-2] > values[-1]:
            v1, v2 = values.pop(), values.pop()
            w1, w2 = weights.pop(), weights.pop()
            n1, n2 = counts.pop(), counts.pop()
            values.append((v1 * w1 + v2 * w2) / (w1 + w2))
            weights.append(w1 + w2)
            counts.append(n1 + n2)
    return np.repeat(np.array(values), counts)


def isotonic(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    order = np.argsort(x, kind="stable")
    xs, ys = x[order], y[order]
    unique_x, inverse, counts = np.unique(xs, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=ys)
    fitted = pava(sums / counts, counts)
    keep = np.ones(len(fitted), dtype=bool)
    if len(fitted) > 2:
        keep[1:-1] = (fitted[1:-1] != fitted[:-2]) | (fitted[1:-1] != fitted[2:])
    return unique_x[keep], fitted[keep]


def fit_additive(print_area, color_area, price):
    mu = float(price.mean())
    f_print = np.zeros_like(price)
    f_color = np.zeros_like(price)
    knots_print = values_print = knots_color = values_color = None
    for _ in range(MAX_ITERATIONS):
        previous = f_print.copy()
        knots_print, values_print = isotonic(print_area, price - mu - f_color)
        f_print = np.interp(print_area, knots_print, values_print)
        knots_color, values_color = isotonic(color_area, price - mu - f_print)
        f_color = np.interp(color_area, knots_color, values_color)
        if np.abs(f_print - previous).max() < TOLERANCE:
            break
    else:
        raise RuntimeError(f"backfit did not converge in {MAX_ITERATIONS} iterations")
    return mu, knots_print, values_print, knots_color, values_color


def _round6(values):
    return [round(float(v), 6) for v in values]


def fit(rows):
    if not rows:
        raise ValueError("cannot fit an empty dataset")
    color = np.array([float(r["color_area"]) for r in rows])
    bw = np.array([float(r["bw_area"]) for r in rows])
    price = np.array([float(r["price"]) for r in rows])
    mu, kp, vp, kc, vc = fit_additive(color + bw, color, price)
    return {
        "intercept": mu,
        "print_thresholds": _round6(kp),
        "print_values": _round6(vp),
        "color_thresholds": _round6(kc),
        "color_values": _round6(vc),
    }


def evaluate(model, rows, config):
    from pricing import page_price

    errors = []
    for r in rows:
        color_cov = float(r["color_area"]) / 100.0
        bw_cov = float(r["bw_area"]) / 100.0
        predicted = page_price(model, color_cov, bw_cov, config)
        errors.append(abs(predicted - float(r["price"])))
    arr = np.array(errors) if errors else np.array([0.0])
    return {
        "n_rows": len(rows),
        "mean_abs_error": float(arr.mean()),
        "max_abs_error": float(arr.max()),
        "p95_abs_error": float(np.percentile(arr, 95)),
    }
```

- [ ] **Step 4: Rewire `tools_fit_model.py` to use `model_fit.fit`**

Replace its private `pava`/`isotonic`/`apply_isotonic`/`fit_additive` with `from model_fit import fit`. Keep `load_dataset()` and the artifact-writing `main()`; replace the `fit_additive(...)` call with:

```python
model = fit([
    {"bw_area": float(r["bw_area"]), "color_area": float(r["color_area"]), "price": float(r["price"])}
    for r in csv.DictReader(DATASET.open())
])
# then write model["intercept"], model["print_thresholds"], etc.
```

Keep the output format identical so `tests/test_pricing_model.py` (dataset-hash) still passes. Run `python3 tools_fit_model.py` and confirm `git diff --stat pricing_model_data.py` is empty.

- [ ] **Step 5: Run tests, lint, commit**

```bash
pytest tests/test_model_fit.py tests/test_pricing_model.py -v
make lint
git add model_fit.py tools_fit_model.py tests/test_model_fit.py
git commit -m "refactor: extract isotonic fit/evaluate core into model_fit"
```

---

### Task 2: `model_store.py` + model-aware pricing

**Files:**
- Create: `model_store.py`
- Modify: `pricing.py`, `pricing_model.py`, `pricecounter.py`
- Test: `tests/test_model_store.py`
- Modify: `tests/test_pricing.py`

**Interfaces:**
- Produces: `model_store.get_active_model() -> dict`, `model_store.reset_cache()` (tests), `model_store.baked_model() -> dict`.
- `pricing.page_price(model, color_coverage, bw_coverage, config) -> int`.
- `pricing.calculate_price(color_coverage, bw_coverage, config=None, model=None) -> dict` (unchanged keys).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model_store.py
import model_store


def test_falls_back_to_baked_model_when_fetch_fails(monkeypatch):
    model_store.reset_cache()
    monkeypatch.setattr(model_store.artivity_client, "get_active_model",
                        lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    model = model_store.get_active_model()
    assert "intercept" in model and model["print_thresholds"]


def test_uses_fetched_model_and_caches(monkeypatch):
    model_store.reset_cache()
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return {
            "id": "v1", "intercept": 1000.0,
            "print_thresholds": [0, 50], "print_values": [0, 100],
            "color_thresholds": [0, 50], "color_values": [0, 200],
        }

    monkeypatch.setattr(model_store.artivity_client, "get_active_model", fake)
    first = model_store.get_active_model()
    second = model_store.get_active_model()
    assert calls["n"] == 1
    assert first["intercept"] == 1000.0
    assert second is first
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_model_store.py -v`
Expected: FAIL (`ModuleNotFoundError: model_store`).

- [ ] **Step 3: Create `model_store.py`**

```python
"""Runtime access to the active pricing model with a baked fallback.

Fetches the active model from artivity-server, caches it per version with a
short TTL, and degrades to the last known model or the baked artifact so the
price path never fails.
"""

import time

import artivity_client
from config import Config
from pricing_model_data import (
    COLOR_AREA_THRESHOLDS,
    COLOR_AREA_VALUES,
    INTERCEPT,
    PRINT_AREA_THRESHOLDS,
    PRINT_AREA_VALUES,
)

_cache = {"model": None, "version_id": None, "fetched_at": 0.0}


def baked_model():
    return {
        "intercept": INTERCEPT,
        "print_thresholds": list(PRINT_AREA_THRESHOLDS),
        "print_values": list(PRINT_AREA_VALUES),
        "color_thresholds": list(COLOR_AREA_THRESHOLDS),
        "color_values": list(COLOR_AREA_VALUES),
    }


def _normalize(data):
    return {
        "intercept": float(data["intercept"]),
        "print_thresholds": list(data["print_thresholds"]),
        "print_values": list(data["print_values"]),
        "color_thresholds": list(data["color_thresholds"]),
        "color_values": list(data["color_values"]),
    }


def reset_cache():
    _cache.update(model=None, version_id=None, fetched_at=0.0)


def get_active_model(force=False):
    now = time.monotonic()
    fresh = now - _cache["fetched_at"] < Config.MODEL_CACHE_TTL_SECONDS
    if not force and _cache["model"] is not None and fresh:
        return _cache["model"]
    try:
        data = artivity_client.get_active_model()
        if data:
            model = _normalize(data)
            _cache.update(model=model, version_id=data.get("id"), fetched_at=now)
            return model
    except Exception:
        pass
    if _cache["model"] is not None:
        return _cache["model"]
    return baked_model()
```

- [ ] **Step 4: Refactor `pricing_model.py` to keep the baked latent helper, and `pricing.py` to take a model**

`pricing_model.py`:

```python
"""Latent price from an explicit model dict (see model_store.baked_model)."""

import numpy as np


def latent_price(model, print_area_pct, color_area_pct):
    print_term = np.interp(print_area_pct, model["print_thresholds"], model["print_values"])
    color_term = np.interp(color_area_pct, model["color_thresholds"], model["color_values"])
    return float(model["intercept"] + print_term + color_term)
```

`pricing.py`:

```python
from config import Config
from model_store import get_active_model
from pricing_model import latent_price


def ladder_round(price, step):
    if step <= 0:
        return int(price)
    return round(price / step) * step


def page_price(model, color_coverage, bw_coverage, config):
    color_pct = color_coverage * 100
    print_pct = (color_coverage + bw_coverage) * 100
    raw = latent_price(model, print_pct, color_pct)
    floor = config.PRICE_FLOOR_BW if color_pct == 0 else config.PRICE_FLOOR_COLOR
    price = max(ladder_round(max(raw, floor), config.PRICE_STEP), floor)
    if config.PRICE_CAP is not None:
        price = min(price, config.PRICE_CAP)
    return price


def calculate_price(color_coverage, bw_coverage, config=None, model=None):
    if config is None:
        config = Config()
    if model is None:
        model = get_active_model()
    page = page_price(model, color_coverage, bw_coverage, config)
    bw_only = page_price(model, 0.0, bw_coverage, config)
    return {"price": page, "bw_price": bw_only, "color_price": max(0, page - bw_only)}
```

Update `pricecounter.getprice_detail` to fetch the model once and pass it:

```python
from model_store import get_active_model

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
        details.append({
            "index": i + 1,
            "print_pct": round(print_pct, 4),
            "color_pct": round(color_pct, 4),
            "bw_pct": round(bw_cov * 100, 4),
            "latent": round(float(latent_price(model, print_pct, color_pct)), 2),
            "bw_price": pricing["bw_price"],
            "color_price": pricing["color_price"],
            "price": pricing["price"],
        })
    return details
```

Update `tests/test_pricing.py` to call `calculate_price(cov, bw, config, model=model_store.baked_model())` so it does not hit the network.

- [ ] **Step 5: Run tests, lint, commit**

```bash
pytest tests/test_model_store.py tests/test_pricing.py tests/test_pricecounter.py -v
make lint
git add model_store.py pricing.py pricing_model.py pricecounter.py tests/test_model_store.py tests/test_pricing.py
git commit -m "feat: model_store with cache/fallback; model-aware pricing"
```

---

### Task 3: `artivity_client.py` (stdlib HTTP)

**Files:**
- Create: `artivity_client.py`
- Modify: `config.py`
- Test: `tests/test_artivity_client.py`

**Interfaces:**
- Produces: `login(email, password) -> dict`, `refresh(refresh_token) -> dict`, `logout(token) -> None`, `me(token) -> dict`, `get_active_model() -> dict | None`, `get(path, token) -> dict`, `post(path, token, body) -> dict`, `service_post(path, body) -> dict`.
- All raise `artivity_client.ArtivityError(status, code, detail)` on non-2xx.

- [ ] **Step 1: Add config envs**

```python
# config.py (append to Config)
    ARTIVITY_SERVER_URL = os.environ.get("ARTIVITY_SERVER_URL", "").rstrip("/")
    PRINT_PRICING_SERVICE_TOKEN = os.environ.get("PRINT_PRICING_SERVICE_TOKEN", "")
    OPERATOR_SESSION_SECRET = os.environ.get("OPERATOR_SESSION_SECRET", "")
    MODEL_CACHE_TTL_SECONDS = int(os.environ.get("MODEL_CACHE_TTL_SECONDS", "60"))
    OPERATOR_COOKIE_SECURE = os.environ.get("OPERATOR_COOKIE_SECURE", "true").lower() == "true"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_artivity_client.py
import json

import pytest

import artivity_client


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_login_posts_credentials_and_returns_envelope(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        return FakeResponse(200, {"data": {"token": "t", "refresh_token": "r", "user": {"id": "u"}}})

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    out = artivity_client.login("owner@mail.test", "secret")
    assert out["token"] == "t"
    assert seen["url"].endswith("/login")
    assert seen["body"] == {"email": "owner@mail.test", "password": "secret"}


def test_get_active_model_returns_none_on_404(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(404, {"error": {"message": "not found"}})

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    assert artivity_client.get_active_model() is None


def test_error_raises_artivity_error(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(401, {"error": {"message": "unauthorized"}})

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    with pytest.raises(artivity_client.ArtivityError) as exc:
        artivity_client.me("bad")
    assert exc.value.status == 401
```

- [ ] **Step 3: Implement `artivity_client.py`**

```python
"""Minimal stdlib client for artivity-server. No third-party HTTP dependency."""

import json
import urllib.error
import urllib.request

from config import Config

# Indirection so tests can monkeypatch a single symbol.
_urlopen = urllib.request.urlopen


class ArtivityError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _request(method, path, token=None, body=None, service=False, timeout=15):
    if not Config.ARTIVITY_SERVER_URL:
        raise ArtivityError(503, "ARTIVITY_SERVER_URL is not configured")
    url = Config.ARTIVITY_SERVER_URL + path
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    if service:
        request.add_header("X-API-Key", Config.PRINT_PRICING_SERVICE_TOKEN)
    try:
        with _urlopen(request, timeout) as response:
            payload = json.loads(response.read() or b"{}")
            return payload.get("data")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        try:
            detail = json.loads(err.read()).get("error", {}).get("message", str(err))
        except Exception:
            detail = str(err)
        raise ArtivityError(err.code, detail) from err
    except urllib.error.URLError as err:
        raise ArtivityError(0, str(err)) from err


def get(path, token):
    return _request("GET", "/api/v1" + path, token=token)


def post(path, token, body=None):
    return _request("POST", "/api/v1" + path, token=token, body=body if body is not None else {})


def patch(path, token, body):
    return _request("PATCH", "/api/v1" + path, token=token, body=body)


def delete(path, token):
    return _request("DELETE", "/api/v1" + path, token=token)


def service_post(path, body):
    return _request("POST", "/api/v1" + path, body=body, service=True)


def login(email, password):
    return _request("POST", "/login", body={"email": email, "password": password})


def refresh(refresh_token):
    return _request("POST", "/refresh", body={"refresh_token": refresh_token})


def logout(token):
    _request("POST", "/logout", token=token, body={})


def me(token):
    return get("/users/me", token)


def get_active_model():
    return _request("GET", "/api/v1/print-pricing/active-model", service=True)
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
pytest tests/test_artivity_client.py -v
make lint
git add artivity_client.py config.py tests/test_artivity_client.py
git commit -m "feat: stdlib artivity-server client and config envs"
```

---

### Task 4: Owner session auth routes

**Files:**
- Create: `label_auth.py`
- Modify: `app.py`
- Test: `tests/test_label_auth.py`

**Interfaces:**
- Produces: `label_auth.register(app)` registering `POST /api/label/auth/login`, `GET /api/label/auth/me`, `POST /api/label/auth/logout`.
- Produces: `label_auth.require_owner(fn)` decorator (used by Task 5).
- Session keys: `token`, `refresh_token`, `user`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_label_auth.py
import pytest

import artivity_client
import label_auth
from app import create_app


class TestConfig:
    TESTING = True
    UPLOAD_FOLDER = "/tmp/api-model-regression-test"
    API_KEY = "test-key"
    MAX_CONTENT_LENGTH = 1024 * 1024
    MAX_PAGES = 10
    PRICE_STEP = 250
    PRICE_CAP_RAW = "3000"
    PRICE_FLOOR_BW = 300
    PRICE_FLOOR_COLOR = 500
    OPERATOR_SESSION_SECRET = "test-secret"
    OPERATOR_COOKIE_SECURE = False
    MODEL_CACHE_TTL_SECONDS = 60
    ARTIVITY_SERVER_URL = "http://artivity.test"
    PRICE_CAP = 3000


@pytest.fixture()
def client(monkeypatch):
    app = create_app(TestConfig)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return app.test_client()


def test_login_rejects_non_owner(client, monkeypatch):
    monkeypatch.setattr(artivity_client, "login",
                        lambda e, p: {"token": "t", "refresh_token": "r",
                                      "user": {"id": "u", "role": {"name": "kasir"}}})
    resp = client.post("/api/label/auth/login", json={"email": "a@b.c", "password": "x"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 403


def test_login_sets_session_for_owner(client, monkeypatch):
    monkeypatch.setattr(artivity_client, "login",
                        lambda e, p: {"token": "t", "refresh_token": "r",
                                      "user": {"id": "u", "role": {"name": "owner"}}})
    resp = client.post("/api/label/auth/login", json={"email": "a@b.c", "password": "x"},
                       headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    me = client.get("/api/label/auth/me")
    assert me.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_label_auth.py -v`
Expected: FAIL (404).

- [ ] **Step 3: Implement `label_auth.py`**

```python
"""Owner session auth: proxy login to artivity-server, keep a signed cookie."""

from functools import wraps

from flask import jsonify, request, session

import artivity_client


def _is_owner(user):
    role = (user or {}).get("role") or {}
    return role.get("name") == "owner"


def require_owner(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("X-Requested-With") != "XMLHttpRequest":
                return jsonify({"error": "csrf", "detail": "missing X-Requested-With"}), 403
        if not session.get("token"):
            return jsonify({"error": "unauthorized", "detail": "not logged in"}), 401
        return fn(*args, **kwargs)

    return wrapper


def register(app):
    @app.post("/api/label/auth/login")
    def login():
        body = request.get_json(silent=True) or {}
        try:
            result = artivity_client.login(body.get("email", ""), body.get("password", ""))
        except artivity_client.ArtivityError as err:
            return jsonify({"error": "unauthorized", "detail": err.message}), 401
        if not _is_owner(result.get("user")):
            return jsonify({"error": "forbidden", "detail": "khusus owner"}), 403
        session["token"] = result["token"]
        session["refresh_token"] = result.get("refresh_token", "")
        session["user"] = result.get("user", {})
        return jsonify({"user": session["user"]})

    @app.get("/api/label/auth/me")
    @require_owner
    def me():
        return jsonify({"user": session.get("user", {})})

    @app.post("/api/label/auth/logout")
    @require_owner
    def logout():
        try:
            artivity_client.logout(session.get("token"))
        except artivity_client.ArtivityError:
            pass
        session.clear()
        return jsonify({"ok": True})
```

- [ ] **Step 4: Wire into the app factory**

```python
# app.py — inside create_app, after register_routes(app):
    app.secret_key = app.config.get("OPERATOR_SESSION_SECRET") or os.urandom(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=bool(app.config.get("OPERATOR_COOKIE_SECURE", True)),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    from label_auth import register as register_label_auth
    register_label_auth(app)
```

- [ ] **Step 5: Run tests, lint, commit**

```bash
pytest tests/test_label_auth.py -v
make lint
git add label_auth.py app.py tests/test_label_auth.py
git commit -m "feat: owner session auth routes"
```

---

### Task 5: Labeling proxy routes

**Files:**
- Create: `label_routes.py`
- Modify: `app.py`
- Test: `tests/test_label_routes.py`

**Interfaces:**
- Consumes: `label_auth.require_owner`, `pricecounter.render_page/analyze_page`, `artivity_client`.
- Produces routes (all owner): `POST /api/label/samples` (multipart `file`), `GET /api/label/samples`, `GET /api/label/samples/<id>`, `DELETE /api/label/samples/<id>`, `PATCH /api/label/pages/<id>`, `POST /api/label/retrain`, `POST /api/label/model-versions/<id>/activate`.
- Flask forwards `session["token"]` to artivity-server for every call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_label_routes.py
import io

import pytest

import artivity_client
from app import create_app


class TestConfig:
    TESTING = True
    UPLOAD_FOLDER = "/tmp/api-model-regression-test"
    API_KEY = "test-key"
    MAX_CONTENT_LENGTH = 1024 * 1024
    MAX_PAGES = 10
    PRICE_STEP = 250
    PRICE_CAP_RAW = "3000"
    PRICE_FLOOR_BW = 300
    PRICE_FLOOR_COLOR = 500
    OPERATOR_SESSION_SECRET = "test-secret"
    OPERATOR_COOKIE_SECURE = False
    MODEL_CACHE_TTL_SECONDS = 60
    ARTIVITY_SERVER_URL = "http://artivity.test"
    PRICE_CAP = 3000


@pytest.fixture()
def client(monkeypatch):
    app = create_app(TestConfig)
    app.config.update(TESTING=True, SECRET_KEY="test-secret")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["token"] = "owner-token"
        sess["user"] = {"id": "u", "role": {"name": "owner"}}
    return client


def test_patch_page_forwards_price_and_token(client, monkeypatch):
    captured = {}

    def fake_patch(path, token, body):
        captured.update(path=path, token=token, body=body)
        return {"id": "p1", "labeled_price": body["labeled_price"]}

    monkeypatch.setattr(artivity_client, "patch", fake_patch)
    resp = client.patch("/api/label/pages/p1", json={"labeled_price": 1500},
                        headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    assert captured["token"] == "owner-token"
    assert captured["path"] == "/print-pricing/pages/p1"
    assert captured["body"] == {"labeled_price": 1500}


def test_retrain_proxies_to_go(client, monkeypatch):
    monkeypatch.setattr(artivity_client, "post",
                        lambda path, token, body: {"id": "v1", "status": "candidate"})
    resp = client.post("/api/label/retrain", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    assert resp.get_json()["id"] == "v1"
```

- [ ] **Step 2: Implement `label_routes.py`**

```python
"""Owner labeling proxy: coverage in Flask, persistence in artivity-server."""

import base64
import io
import os
import uuid

import pypdfium2 as pdfium
from flask import current_app, jsonify, request, session

import artivity_client
from label_auth import require_owner
from pricecounter import analyze_page, render_page

THUMBNAIL_WIDTH = 160


def _thumbnail_base64(pil_image):
    thumb = pil_image.copy()
    thumb.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 4))
    buffer = io.BytesIO()
    thumb.convert("RGB").save(buffer, format="JPEG", quality=70)
    return base64.b64encode(buffer.getvalue()).decode()


def _compute_pages(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    pages = []
    for i in range(len(pdf)):
        image = render_page(pdf, i)
        color_cov, bw_cov = analyze_page(image)
        pages.append({
            "page_number": i + 1,
            "bw_area": round(bw_cov * 100, 4),
            "color_area": round(color_cov * 100, 4),
            "thumbnail_base64": _thumbnail_base64(image),
        })
    return pages


def _token():
    return session.get("token")


def register(app):
    @app.post("/api/label/samples")
    @require_owner
    def create_sample():
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "bad_request", "detail": "no file"}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "bad_request", "detail": "file type not allowed"}), 400

        path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"sample-{uuid.uuid4().hex}.pdf")
        file.save(path)
        magic_ok = open(path, "rb").read(5) == b"%PDF-"
        if not magic_ok:
            os.remove(path)
            return jsonify({"error": "invalid_pdf", "detail": "not a PDF"}), 400
        try:
            page_count = len(pdfium.PdfDocument(path))
            if page_count > current_app.config["MAX_PAGES"]:
                return jsonify({"error": "too_many_pages",
                                "detail": f"max {current_app.config['MAX_PAGES']} pages"}), 413
            pages = _compute_pages(path)
        finally:
            if os.path.exists(path):
                os.remove(path)

        try:
            sample = artivity_client.post("/print-pricing/samples", _token(), {
                "original_filename": file.filename,
                "page_count": page_count,
                "pages": pages,
            })
        except artivity_client.ArtivityError as err:
            return jsonify({"error": "artivity_error", "detail": err.message}), err.status or 502
        return jsonify(sample)

    @app.get("/api/label/samples")
    @require_owner
    def list_samples():
        return jsonify(artivity_client.get("/print-pricing/samples", _token()))

    @app.get("/api/label/samples/<sample_id>")
    @require_owner
    def get_sample(sample_id):
        return jsonify(artivity_client.get(f"/print-pricing/samples/{sample_id}", _token()))

    @app.delete("/api/label/samples/<sample_id>")
    @require_owner
    def delete_sample(sample_id):
        return jsonify(artivity_client.delete(f"/print-pricing/samples/{sample_id}", _token()))

    @app.patch("/api/label/pages/<page_id>")
    @require_owner
    def patch_page(page_id):
        body = request.get_json(silent=True) or {}
        return jsonify(artivity_client.patch(f"/print-pricing/pages/{page_id}", _token(),
                                             {"labeled_price": body.get("labeled_price")}))

    @app.post("/api/label/retrain")
    @require_owner
    def retrain():
        try:
            return jsonify(artivity_client.post("/print-pricing/retrain", _token(), {}))
        except artivity_client.ArtivityError as err:
            return jsonify({"error": "artivity_error", "detail": err.message}), err.status or 502

    @app.post("/api/label/model-versions/<version_id>/activate")
    @require_owner
    def activate(version_id):
        return jsonify(artivity_client.post(
            f"/print-pricing/model-versions/{version_id}/activate", _token(), {}))
```

Note: `artivity_client.patch` and `artivity_client.delete` are defined in Task 3.

- [ ] **Step 3: Register in the app factory**

```python
# app.py — after register_label_auth(app):
    from label_routes import register as register_label_routes
    register_label_routes(app)
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
pytest tests/test_label_routes.py -v
make lint
git add label_routes.py artivity_client.py app.py tests/test_label_routes.py
git commit -m "feat: owner labeling proxy routes"
```

---

### Task 6: `/internal/train` service endpoint

**Files:**
- Create: `train_routes.py`
- Modify: `app.py`
- Test: `tests/test_internal_train.py`

**Interfaces:**
- Consumes: `model_fit.fit/evaluate`, `model_store.baked_model`, `config.Config`.
- Produces: `POST /internal/train` returning `{"data": {intercept, print_thresholds, print_values, color_thresholds, color_values, metrics}}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_internal_train.py
import pytest

from app import create_app


class TestConfig:
    TESTING = True
    UPLOAD_FOLDER = "/tmp/api-model-regression-test"
    API_KEY = "test-key"
    MAX_CONTENT_LENGTH = 1024 * 1024
    MAX_PAGES = 10
    PRICE_STEP = 250
    PRICE_CAP_RAW = "3000"
    PRICE_FLOOR_BW = 300
    PRICE_FLOOR_COLOR = 500
    PRINT_PRICING_SERVICE_TOKEN = "svc-token"
    OPERATOR_SESSION_SECRET = "x"
    OPERATOR_COOKIE_SECURE = False
    MODEL_CACHE_TTL_SECONDS = 60
    ARTIVITY_SERVER_URL = "http://artivity.test"
    PRICE_CAP = 3000


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, SECRET_KEY="x")
    return app.test_client()


ROWS = [{"bw_area": 1.0, "color_area": i * 5.0, "price": 500.0 + i * 100} for i in range(1, 21)]


def test_rejects_missing_service_token(client):
    resp = client.post("/internal/train", json={"rows": ROWS})
    assert resp.status_code in (401, 403)


def test_trains_and_returns_coefficients(client):
    resp = client.post("/internal/train", json={"rows": ROWS},
                       headers={"X-API-Key": "svc-token"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["print_thresholds"] == sorted(data["print_thresholds"])
    assert data["metrics"]["n_rows"] == len(ROWS)
```

- [ ] **Step 2: Implement `train_routes.py`**

```python
"""Service-to-service training endpoint."""

import hmac

from flask import current_app, jsonify, request

from model_fit import evaluate, fit


def _authorized():
    expected = current_app.config.get("PRINT_PRICING_SERVICE_TOKEN", "")
    if not expected:
        return False
    given = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def register(app):
    @app.post("/internal/train")
    def train():
        if not _authorized():
            return jsonify({"error": "forbidden", "detail": "invalid service token"}), 403
        body = request.get_json(silent=True) or {}
        rows = body.get("rows") or []
        if not rows:
            return jsonify({"error": "bad_request", "detail": "no rows"}), 400

        model = fit(rows)
        metrics = evaluate(model, rows, current_app.config)
        return jsonify({"data": {**model, "metrics": metrics}})
```

- [ ] **Step 3: Register in the app factory and run tests**

```python
# app.py — after register_label_routes(app):
    from train_routes import register as register_train_routes
    register_train_routes(app)
```

```bash
pytest tests/test_internal_train.py -v
make lint
```

- [ ] **Step 4: Commit**

```bash
git add train_routes.py app.py tests/test_internal_train.py
git commit -m "feat: internal training endpoint"
```

---

### Task 7: Docs, env example, full gate

**Files:**
- Modify: `.env.example`, `README.md`, `AGENTS.md`

- [ ] **Step 1: Document the new env vars**

```bash
# .env.example (append)
ARTIVITY_SERVER_URL=https://artivity-server.example
PRINT_PRICING_SERVICE_TOKEN=change-me-print-pricing-service-token
OPERATOR_SESSION_SECRET=change-me-long-random-string
MODEL_CACHE_TTL_SECONDS=60
OPERATOR_COOKIE_SECURE=true
```

- [ ] **Step 2: Update README/AGENTS architecture notes**

Add a short "Operator labeling & retrain" section: login via artivity-server, samples/labels stored there, `/internal/train` service endpoint, active-model cache + baked fallback, and the new env vars.

- [ ] **Step 3: Run the full gate**

```bash
make lint && make test && make web-build
```
Expected: all pass. Confirm `pytest tests/test_pricing_model.py` still green (baked artifact unchanged).

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md AGENTS.md
git commit -m "docs: operator labeling, retrain, and model-serving config"
```

---

## Notes for the executor

- `tests/conftest.py` builds the app for existing tests; do not change its `Config` behavior. New tests pass a local `TestConfig` to `create_app`.
- `page_price` and `evaluate` read `PRICE_STEP`, `PRICE_FLOOR_BW`, `PRICE_FLOOR_COLOR`, `PRICE_CAP` off whatever config object they are handed; the app passes `current_app.config`, tests pass `TestConfig`. Keep those four attribute names identical to `config.Config`.
- Keep `pricing_model.py`'s `latent_price` signature change (`model` first) consistent everywhere it is imported (`pricecounter.py`, `pricing.py`, `tests/test_pricing_model.py` if it calls it).
- Do not add `requests`; `artivity_client` is the single outbound HTTP surface.
