from .base import *
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)


DEBUG = False

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Security hardening
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Static files (common production setup)
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Recommended: Whitenoise (if not using Nginx for static)
INSTALLED_APPS = ["whitenoise.runserver_nostatic"] + INSTALLED_APPS
MIDDLEWARE = MIDDLEWARE.copy()
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DATABASES["default"].update({
    "NAME": os.getenv("DB_NAME"),
    "USER": os.getenv("DB_USER"),
    "PASSWORD": os.getenv("DB_PASSWORD"),
    "HOST": os.getenv("DB_HOST"),
    "PORT": os.getenv("DB_PORT")
})