"""Configuration objects (12-factor: everything overridable by env vars)."""

import os
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bool(name, default):
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    BASE_DIR = BASE_DIR
    IS_PRODUCTION = False
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/flyte.db")
    LEGACY_JSON = os.environ.get("LEGACY_JSON", os.path.join(BASE_DIR, "airline_db.json"))   # imported once if present
    SEED_DEMO = _bool("SEED_DEMO", True)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    OUTBOX_PATH = os.environ.get("OUTBOX_PATH", os.path.join(BASE_DIR, "data", "outbox.log"))
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "Flyte <hello@flyte.ng>")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    JSON_SORT_KEYS = False
    TESTING = False


class ProductionConfig(Config):
    IS_PRODUCTION = True
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    SEED_DEMO = _bool("SEED_DEMO", False)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    DATABASE_URL = "sqlite:///:memory:"
    SEED_DEMO = False
    WTF_CSRF_ENABLED = False


def get_config():
    return ProductionConfig if os.environ.get("FLASK_ENV") == "production" or os.environ.get("APP_ENV") == "production" else Config
