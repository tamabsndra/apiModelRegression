import os
import time

from flask import Flask

from config import Config

ORPHAN_MAX_AGE_SECONDS = 3600


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    sweep_uploads(app.config["UPLOAD_FOLDER"])

    from routes import register_routes

    register_routes(app)

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
