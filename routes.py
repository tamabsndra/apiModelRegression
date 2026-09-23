import hmac
import os
import uuid

import pypdfium2 as pdfium
from flask import jsonify, request

from config import Config

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_pdf(filepath):
    """Validate magic bytes and page count. Returns (valid, err_msg, page_count)."""
    with open(filepath, "rb") as f:
        magic = f.read(5)
    if magic != b"%PDF-":
        os.unlink(filepath)
        return False, "Not a valid PDF", 0
    try:
        pdf = pdfium.PdfDocument(filepath)
        page_count = len(pdf)
        pdf.close()
        if page_count == 0:
            os.unlink(filepath)
            return False, "PDF has no pages", 0
    except Exception:
        os.unlink(filepath)
        return False, "Malformed PDF", 0
    return True, None, page_count


def register_routes(app):
    @app.before_request
    def check_content_length():
        if request.content_length and request.content_length > Config.MAX_CONTENT_LENGTH:
            return jsonify({"error": "payload_too_large", "detail": "File too large"}), 413

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "unauthorized", "detail": "Invalid or missing API key"}), 401

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "payload_too_large", "detail": "File too large"}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal_error", "detail": "An unexpected error occurred"}), 500

    @app.route("/api/v3/upload", methods=["POST"])
    def upload_file():
        api_key = request.headers.get("api-key", "")
        if not Config.API_KEY or not hmac.compare_digest(
            api_key.encode("latin-1", errors="replace"),
            Config.API_KEY.encode("latin-1", errors="replace"),
        ):
            return jsonify({"error": "unauthorized", "detail": "Invalid or missing API key"}), 401

        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "bad_request", "detail": "No file part in the request"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "bad_request", "detail": "File type not allowed"}), 400

        file_ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        safe_name = f"{uuid.uuid4().hex}{file_ext}"
        filepath = os.path.join(Config.UPLOAD_FOLDER, safe_name)
        file.save(filepath)

        valid, err_msg, page_count = validate_pdf(filepath)
        if not valid:
            return jsonify({"error": "invalid_pdf", "detail": err_msg}), 400

        if page_count > Config.MAX_PAGES:
            os.unlink(filepath)
            return jsonify(
                {"error": "too_many_pages", "detail": f"Max {Config.MAX_PAGES} pages"}
            ), 413

        try:
            from pricecounter import getpage, getprice

            price = getprice(filepath)
            page = getpage(filepath)
            return jsonify(
                {
                    "message": "File processed",
                    "price": price,
                    "page": page,
                    "bw_price": 300 * page,
                }
            ), 200
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"status": "ok"}), 200
