import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("ILMNOTE_SECRET", "ilmnote-local-secret-change-me-please")
    DATABASE = os.path.join(BASE_DIR, "ilmnote.db")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "covers")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024   # 8 MB
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
    DEBUG = False