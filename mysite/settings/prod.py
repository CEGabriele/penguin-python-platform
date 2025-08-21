import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

from .base import *
from pathlib import Path

DEBUG = False
USES_S3=True
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")


AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ca-central-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True  # media should be private → signed URLs
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}  # 1 day

# Use our custom storages
DEFAULT_FILE_STORAGE = "project.storages.MediaRootS3Boto3Storage"
STATICFILES_STORAGE = "project.storages.StaticRootS3Boto3Storage"

# Public static (via S3 or CloudFront). If using S3 domain:
STATIC_URL = f"https://homework-dashboard-resources.s3.amazonaws.com/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_FILES_DIRS=[BASE_DIR / "static"]

# Media signed URLs; django-storages will sign when accessing file.url
MEDIA_URL = f"https://homework-dashboard-resources.s3.amazonaws.com/media/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "ERROR"},
}
