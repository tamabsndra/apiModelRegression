import os
import time

from flask import Flask

from config import Config

ORPHAN_MAX_AGE_SECONDS = 3600


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    _remove_orphan_uploads(app.config["UPLOAD_FOLDER"])

    from routes import register_routes

    register_routes(app)

    return app


def _remove_orphan_uploads(folder):
    """Delete stale upload files (mtime older than ORPHAN_MAX_AGE_SECONDS).

    Never raises: a broken upload folder must not crash app startup.
    """
    try:
        now = time.time()
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and now - os.path.getmtime(path) > ORPHAN_MAX_AGE_SECONDS:
                os.remove(path)
    except OSError:
        pass
