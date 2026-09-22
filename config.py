import os


class Config:
    API_KEY = os.environ.get("API_KEY", "")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", str(50 * 1024 * 1024)))

    PRICE_COEFF_COLOR = float(os.environ.get("PRICE_COEFF_COLOR", "19.59733806"))
    PRICE_COEFF_BW = float(os.environ.get("PRICE_COEFF_BW", "7.05360083"))
    PRICE_INTERCEPT = float(os.environ.get("PRICE_INTERCEPT", "191.3642"))
    PRICE_STEP = int(os.environ.get("PRICE_STEP", "250"))
    PRICE_CAP_RAW = os.environ.get("PRICE_CAP", "3000")
    PRICE_FLOOR_BW = int(os.environ.get("PRICE_FLOOR_BW", "300"))
    PRICE_FLOOR_COLOR = int(os.environ.get("PRICE_FLOOR_COLOR", "500"))

    @property
    def PRICE_CAP(self):
        if self.PRICE_CAP_RAW == "" or self.PRICE_CAP_RAW is None:
            return None
        return int(self.PRICE_CAP_RAW)
