from .base import *
from dotenv import load_dotenv
load_dotenv()

DATABASES["default"].update({
    "NAME": os.getenv("DEV_DB_NAME"),
    "USER": os.getenv("DEV_DB_USERNAME"),
    "PASSWORD": os.getenv("DB_PASSWORD"),
})

DEBUG = True
ALLOWED_HOSTS = []


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
