import io

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
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers={"api-key": "wrong"})
        assert resp.status_code == 401

    def test_non_pdf_rejected(self, client, auth_header):
        data = {"file": (io.BytesIO(b"not a pdf"), "test.txt")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 400

    def test_valid_bw_pdf(self, client, auth_header, bw_pdf):
        data = {"file": (bw_pdf, "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 200
        body = resp.json
        assert "price" in body
        assert "page" in body
        assert "bw_price" in body
        assert body["page"] == 1

    def test_valid_color_pdf(self, client, auth_header, color_pdf):
        data = {"file": (color_pdf, "test.pdf")}
        resp = client.post("/api/v3/upload", data=data, content_type="multipart/form-data",
                           headers=auth_header)
        assert resp.status_code == 200
        body = resp.json
        assert body["price"] >= 500
