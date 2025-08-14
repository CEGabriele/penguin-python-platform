
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)
from .base import *
from pathlib import Path

DEBUG = False

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Security hardening
#temporary disable for testing on http
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Static files (common production setup)
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Recommended: Whitenoise (if not using Nginx for static)
INSTALLED_APPS = ["whitenoise.runserver_nostatic"] + INSTALLED_APPS
MIDDLEWARE = MIDDLEWARE.copy()
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


PRIVATE_MEDIA_ROOT = Path("/home/ubuntu/homework_dashboard/private_media")

from django.core.files.storage import FileSystemStorage
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(location=str(PRIVATE_MEDIA_ROOT), base_url=None, *args, **kwargs)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
}