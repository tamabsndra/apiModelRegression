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
