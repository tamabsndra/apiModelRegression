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
    resp = client.patch(
        "/api/label/pages/p1",
        json={"labeled_price": 1500},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    assert captured["token"] == "owner-token"
    assert captured["path"] == "/print-pricing/pages/p1"
    assert captured["body"] == {"labeled_price": 1500}


def test_retrain_proxies_to_go(client, monkeypatch):
    monkeypatch.setattr(
        artivity_client, "post", lambda path, token, body: {"id": "v1", "status": "candidate"}
    )
    resp = client.post("/api/label/retrain", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 200
    assert resp.get_json()["id"] == "v1"
