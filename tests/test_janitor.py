import os
import time

from app import sweep_uploads


class TestSweepUploads:
    def test_keeps_dotfiles(self, tmp_path):
        stale = time.time() - 7200
        gitkeep = tmp_path / ".gitkeep"
        stale_upload = tmp_path / "x.pdf"
        gitkeep.write_text("")
        stale_upload.write_bytes(b"%PDF-1.4")
        os.utime(gitkeep, (stale, stale))
        os.utime(stale_upload, (stale, stale))

        sweep_uploads(tmp_path)

        assert gitkeep.exists()
        assert not stale_upload.exists()

    def test_keeps_fresh_files(self, tmp_path):
        fresh = tmp_path / "fresh.pdf"
        fresh.write_bytes(b"%PDF-1.4")

        sweep_uploads(tmp_path)

        assert fresh.exists()
