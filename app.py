import os
import time

from flask import Flask, send_from_directory

from config import Config

ORPHAN_MAX_AGE_SECONDS = 3600

UI_NOT_BUILT_HTML = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Artivity Print Calculator</title>
</head>
<body style="font-family: system-ui; max-width: 40rem; margin: 4rem auto;
  padding: 0 1.5rem; line-height: 1.6">
<h1>UI belum di-build</h1>
<p>API sudah jalan. Halaman ini muncul karena bundle React belum ada di <code>public/</code>.</p>
<p>Jalankan:</p>
<pre style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1rem"><code>cd web
npm install
npm run build</code></pre>
<p>Endpoint API tetap tersedia: <code>POST /api/v3/upload</code> dan
<code>GET /healthz</code>.</p>
</body>
</html>
"""


def create_app(config_class=Config):
    static_dir = os.path.join(os.path.dirname(__file__), "public")
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    sweep_uploads(app.config["UPLOAD_FOLDER"])

    from routes import register_routes

    register_routes(app)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_ui(path):
        """Serve the built SPA, falling back to build instructions.

        The bundle is a build artifact (public/ is gitignored), so a fresh
        clone has no UI until `cd web && npm run build` runs.
        """
        full = os.path.join(static_dir, path)
        if path and os.path.isfile(full):
            return send_from_directory(static_dir, path)
        index = os.path.join(static_dir, "index.html")
        if os.path.isfile(index):
            return send_from_directory(static_dir, "index.html")
        return UI_NOT_BUILT_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

    return app


def sweep_uploads(folder, max_age_seconds=ORPHAN_MAX_AGE_SECONDS):
    """Delete stale upload files (mtime older than max_age_seconds).

    Dotfiles are never removed: uploads/.gitkeep is tracked in git and
    must survive sweeps (conftest runs create_app against the real
    uploads/ folder before repointing UPLOAD_FOLDER).
    Never raises: a broken upload folder must not crash app startup.
    """
    try:
        now = time.time()
        for name in os.listdir(folder):
            if name.startswith("."):
                continue
            path = os.path.join(folder, name)
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
    except OSError:
        pass
