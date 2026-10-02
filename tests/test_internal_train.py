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


def test_rejects_wrong_service_token(client):
    resp = client.post("/internal/train", json={"rows": ROWS}, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 403


def test_rejects_empty_rows(client):
    resp = client.post("/internal/train", json={"rows": []}, headers={"X-API-Key": "svc-token"})
    assert resp.status_code == 400


def test_rejects_malformed_rows(client):
    resp = client.post(
        "/internal/train",
        json={"rows": [{"bw_area": "oops", "color_area": 1.0, "price": 500.0}]},
        headers={"X-API-Key": "svc-token"},
    )
    assert resp.status_code == 400


def test_trains_and_returns_coefficients(client):
    resp = client.post("/internal/train", json={"rows": ROWS}, headers={"X-API-Key": "svc-token"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["print_thresholds"] == sorted(data["print_thresholds"])
    assert data["metrics"]["n_rows"] == len(ROWS)
