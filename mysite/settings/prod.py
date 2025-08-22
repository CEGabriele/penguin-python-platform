import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from .base import *


DEBUG = False
USE_S3 = True  # optional toggle you can read elsewhere if needed

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# --------------------
# Security (adjust as you prefer)
# --------------------
SECURE_SSL_REDIRECT = False         # consider True in production
SESSION_COOKIE_SECURE = False       # consider True in production
CSRF_COOKIE_SECURE = False          # consider True in production
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --------------------
# AWS / S3 (regional)
# --------------------
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ca-central-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"

AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}  # 1 day

# Static should be public (no signatures); media uses signed URLs
AWS_QUERYSTRING_AUTH = False

# --------------------
# Static / Media URLs
# --------------------
STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
MEDIA_URL  = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"

# Local staging dir required for collectstatic (Django won’t serve from here)
STATIC_ROOT = BASE_DIR / "staticfiles"  # type: ignore[name-defined]

# If you actually have a project-level ./static folder, uncomment:
# STATICFILES_DIRS = [BASE_DIR / "static"]

# --------------------
# Django 4.2+ STORAGES
# --------------------
STORAGES = {
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "static",
            "default_acl": None,
            "file_overwrite": True,
            "querystring_auth": False,  # public static
        },
    },
    "default": {  # MEDIA (private)
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "location": "media",
            "default_acl": "private",
            "file_overwrite": False,
            "querystring_auth": True,   # signed media
        },
    },
}

# --------------------
# Logging
# --------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "ERROR"},
}