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
