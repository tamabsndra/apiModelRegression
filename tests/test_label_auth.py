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
    return app.test_client()


def test_login_rejects_non_owner(client, monkeypatch):
    monkeypatch.setattr(
        artivity_client,
        "login",
        lambda e, p: {
            "token": "t",
            "refresh_token": "r",
            "user": {"id": "u", "role": {"name": "kasir"}},
        },
    )
    resp = client.post(
        "/api/label/auth/login",
        json={"email": "a@b.c", "password": "x"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 403


def test_login_sets_session_for_owner(client, monkeypatch):
    monkeypatch.setattr(
        artivity_client,
        "login",
        lambda e, p: {
            "token": "t",
            "refresh_token": "r",
            "user": {"id": "u", "role": {"name": "owner"}},
        },
    )
    resp = client.post(
        "/api/label/auth/login",
        json={"email": "a@b.c", "password": "x"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    me = client.get("/api/label/auth/me")
    assert me.status_code == 200
