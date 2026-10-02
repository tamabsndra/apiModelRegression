"""Owner labeling proxy: coverage in Flask, persistence in artivity-server."""

import base64
import io
import os
import uuid

import pypdfium2 as pdfium
from flask import current_app, jsonify, request, session

import artivity_client
from label_auth import require_owner
from pricecounter import analyze_page, render_page

THUMBNAIL_WIDTH = 160


def _thumbnail_base64(pil_image):
    thumb = pil_image.copy()
    thumb.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 4))
    buffer = io.BytesIO()
    thumb.convert("RGB").save(buffer, format="JPEG", quality=70)
    return base64.b64encode(buffer.getvalue()).decode()


def _compute_pages(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    pages = []
    for i in range(len(pdf)):
        image = render_page(pdf, i)
        color_cov, bw_cov = analyze_page(image)
        pages.append(
            {
                "page_number": i + 1,
                "bw_area": round(bw_cov * 100, 4),
                "color_area": round(color_cov * 100, 4),
                "thumbnail_base64": _thumbnail_base64(image),
            }
        )
    return pages


def _token():
    return session.get("token")


def _proxy(call):
    try:
        result = call()
    except artivity_client.ArtivityError as err:
        return jsonify({"error": "artivity_error", "detail": err.message}), err.status or 502
    if result is None:
        return jsonify({"error": "not_found", "detail": "not found"}), 404
    return jsonify(result)


def register(app):
    @app.post("/api/label/samples")
    @require_owner
    def create_sample():
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "bad_request", "detail": "no file"}), 400
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "bad_request", "detail": "file type not allowed"}), 400

        path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"sample-{uuid.uuid4().hex}.pdf")
        file.save(path)
        with open(path, "rb") as handle:
            magic_ok = handle.read(5) == b"%PDF-"
        if not magic_ok:
            os.remove(path)
            return jsonify({"error": "invalid_pdf", "detail": "not a PDF"}), 400
        try:
            try:
                page_count = len(pdfium.PdfDocument(path))
            except Exception:
                return jsonify({"error": "invalid_pdf", "detail": "malformed PDF"}), 400
            if page_count > current_app.config["MAX_PAGES"]:
                return jsonify(
                    {
                        "error": "too_many_pages",
                        "detail": f"max {current_app.config['MAX_PAGES']} pages",
                    }
                ), 413
            pages = _compute_pages(path)
        finally:
            if os.path.exists(path):
                os.remove(path)

        return _proxy(
            lambda: artivity_client.post(
                "/print-pricing/samples",
                _token(),
                {
                    "original_filename": file.filename,
                    "page_count": page_count,
                    "pages": pages,
                },
            )
        )

    @app.get("/api/label/samples")
    @require_owner
    def list_samples():
        return _proxy(lambda: artivity_client.get("/print-pricing/samples", _token()))

    @app.get("/api/label/samples/<sample_id>")
    @require_owner
    def get_sample(sample_id):
        return _proxy(lambda: artivity_client.get(f"/print-pricing/samples/{sample_id}", _token()))

    @app.delete("/api/label/samples/<sample_id>")
    @require_owner
    def delete_sample(sample_id):
        return _proxy(
            lambda: artivity_client.delete(f"/print-pricing/samples/{sample_id}", _token())
        )

    @app.patch("/api/label/pages/<page_id>")
    @require_owner
    def patch_page(page_id):
        body = request.get_json(silent=True) or {}
        return _proxy(
            lambda: artivity_client.patch(
                f"/print-pricing/pages/{page_id}",
                _token(),
                {"labeled_price": body.get("labeled_price")},
            )
        )

    @app.post("/api/label/retrain")
    @require_owner
    def retrain():
        return _proxy(lambda: artivity_client.post("/print-pricing/retrain", _token(), {}))

    @app.post("/api/label/model-versions/<version_id>/activate")
    @require_owner
    def activate(version_id):
        return _proxy(
            lambda: artivity_client.post(
                f"/print-pricing/model-versions/{version_id}/activate", _token(), {}
            )
        )
