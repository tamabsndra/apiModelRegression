import io
import json
import urllib.error

import pytest

import artivity_client
from config import Config


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


@pytest.fixture(autouse=True)
def _server_url(monkeypatch):
    monkeypatch.setattr(Config, "ARTIVITY_SERVER_URL", "http://artivity.test")


def _http_error(request, status, payload):
    return urllib.error.HTTPError(
        request.full_url, status, "error", {}, io.BytesIO(json.dumps(payload).encode())
    )


def test_login_posts_credentials_and_returns_envelope(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        return FakeResponse(
            200, {"data": {"token": "t", "refresh_token": "r", "user": {"id": "u"}}}
        )

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    out = artivity_client.login("owner@mail.test", "secret")
    assert out["token"] == "t"
    assert seen["url"].endswith("/login")
    assert seen["body"] == {"email": "owner@mail.test", "password": "secret"}


def test_get_active_model_returns_none_on_404(monkeypatch):
    def fake_urlopen(request, timeout):
        raise _http_error(request, 404, {"error": {"message": "not found"}})

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    assert artivity_client.get_active_model() is None


def test_error_raises_artivity_error(monkeypatch):
    def fake_urlopen(request, timeout):
        raise _http_error(request, 401, {"error": {"message": "unauthorized"}})

    monkeypatch.setattr(artivity_client, "_urlopen", fake_urlopen)
    with pytest.raises(artivity_client.ArtivityError) as exc:
        artivity_client.me("bad")
    assert exc.value.status == 401
