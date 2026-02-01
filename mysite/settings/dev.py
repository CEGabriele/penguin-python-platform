from .base import *
from dotenv import load_dotenv
from pathlib import Path
import os
load_dotenv()

USES_S3=False

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR.parent / "static",
]


DATABASES["default"].update({
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("DB_NAME"),
    "USER": os.getenv("DB_USERNAME"),
    "PASSWORD": os.getenv("DB_PASSWORD"),
    "HOST": os.getenv("DB_HOST"),
    "PORT": os.getenv("DB_PORT"),
})

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost','*']


EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]


INTERNAL_IPS = ["127.0.0.1", "localhost"]


CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dev-no-persist",
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

from django.core.files.storage import FileSystemStorage
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(location=str(MEDIA_ROOT), base_url=None, *args, **kwargs)


SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]