import io

from config import Config


class TestHealthz:
    def test_healthz(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json["status"] == "ok"


class TestUpload:
    def test_missing_api_key(self, client):
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 401

    def test_invalid_api_key(self, client):
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post(
            "/api/v3/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"api-key": "wrong"},
        )
        assert resp.status_code == 401

    def test_nonascii_api_key_is_401_not_500(self, client):
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post(
            "/api/v3/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"api-key": "këy-ñonascii"},
        )
        assert resp.status_code == 401

    def test_empty_api_key_fails_closed(self, client, monkeypatch):
        monkeypatch.setattr(Config, "API_KEY", "")
        data = {"file": (io.BytesIO(b"fake"), "test.pdf")}
        resp = client.post(
            "/api/v3/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"api-key": "anything"},
        )
        assert resp.status_code == 401

    def test_non_pdf_rejected(self, client, auth_header):
        data = {"file": (io.BytesIO(b"not a pdf"), "test.txt")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 400

    def test_valid_bw_pdf(self, client, auth_header, bw_pdf):
        data = {"file": (bw_pdf, "test.pdf")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 200
        body = resp.json
        assert "price" in body
        assert "page" in body
        assert "bw_price" in body
        assert body["page"] == 1
        assert "pages" in body
        assert isinstance(body["pages"], list)
        assert len(body["pages"]) == body["page"]

    def test_valid_bw_pdf_pages_have_detail(self, client, auth_header, bw_pdf):
        data = {"file": (bw_pdf, "test.pdf")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 200
        page = resp.json["pages"][0]
        required = {
            "index",
            "print_pct",
            "color_pct",
            "bw_pct",
            "latent",
            "bw_price",
            "color_price",
            "price",
        }
        assert required.issubset(page.keys())

    def test_bw_price_matches_sum_of_pages(self, client, auth_header, two_page_pdf):
        data = {"file": (two_page_pdf, "test.pdf")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 200
        body = resp.json
        assert body["bw_price"] == sum(p["bw_price"] for p in body["pages"])
        assert body["price"] == sum(p["price"] for p in body["pages"])

    def test_valid_color_pdf(self, client, auth_header, color_pdf):
        data = {"file": (color_pdf, "test.pdf")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 200
        body = resp.json
        assert body["price"] >= 500

    def test_too_many_pages_rejected(self, client, auth_header, two_page_pdf, monkeypatch):
        monkeypatch.setattr(Config, "MAX_PAGES", 1)
        data = {"file": (two_page_pdf, "test.pdf")}
        resp = client.post(
            "/api/v3/upload", data=data, content_type="multipart/form-data", headers=auth_header
        )
        assert resp.status_code == 413
        assert resp.json["error"] == "too_many_pages"
        assert resp.json["detail"] == "Max 1 pages"


class TestStaticUi:
    def test_index_route_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<!doctype html>" in resp.data.lower() or b"<html" in resp.data.lower()


class TestConfigEndpoint:
    def test_config_returns_public_limits(self, client):
        resp = client.get("/api/v3/config")
        assert resp.status_code == 200
        body = resp.json
        for field in (
            "max_pages",
            "max_content_length",
            "price_step",
            "price_cap",
            "price_floor_bw",
            "price_floor_color",
        ):
            assert field in body, f"missing {field}"

    def test_config_never_leaks_api_key(self, client):
        resp = client.get("/api/v3/config")
        assert "api_key" not in resp.json
        assert "API_KEY" not in resp.json

    def test_config_reflects_env_overrides(self, client, monkeypatch):
        monkeypatch.setattr(Config, "MAX_PAGES", 42)
        monkeypatch.setattr(Config, "PRICE_CAP_RAW", "")
        resp = client.get("/api/v3/config")
        assert resp.json["max_pages"] == 42
        assert resp.json["price_cap"] is None


class TestUiFallback:
    def test_unbuilt_ui_explains_how_to_build(self, monkeypatch, tmp_path):
        """A fresh clone has no public/ bundle; the route must explain, not 404."""
        import app as app_module

        monkeypatch.setattr(app_module, "__file__", str(tmp_path / "app.py"))
        fresh = app_module.create_app()
        resp = fresh.test_client().get("/")
        assert resp.status_code == 200
        assert b"npm run build" in resp.data
