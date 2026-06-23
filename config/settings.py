import os
from pathlib import Path
from datetime import timedelta

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-dev-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "channels",
    "storages",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "apps.common",
    "apps.dealers",
    "apps.accounts",
    "apps.vehicles",
    "apps.marketplace",
    "apps.leads",
    "apps.buyers",
    "apps.bookings",
    "apps.billing",
    "apps.platform",
    "apps.core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://autoshowroom:autoshowroom@postgres:5432/autoshowroom",
)

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DATABASE_CONN_MAX_AGE", "600")),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "local-dev-access-key")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "local-dev-secret-key")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or None
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "autoshowroom-local")
AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip() or None
AWS_QUERYSTRING_AUTH = os.getenv("AWS_QUERYSTRING_AUTH", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STATIC_UPLOAD_PREFIX = os.getenv("STATIC_UPLOAD_PREFIX", "static").strip("/")
MEDIA_PUBLIC_BASE_URL = os.getenv("MEDIA_PUBLIC_BASE_URL", "").rstrip("/")
MEDIA_UPLOAD_PREFIX = os.getenv("MEDIA_UPLOAD_PREFIX", "vehicle-media").strip("/")
MEDIA_UPLOAD_URL_EXPIRES_SECONDS = int(
    os.getenv("MEDIA_UPLOAD_URL_EXPIRES_SECONDS", "900")
)

if AWS_S3_CUSTOM_DOMAIN:
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{STATIC_UPLOAD_PREFIX}/"
elif AWS_S3_ENDPOINT_URL:
    STATIC_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/{STATIC_UPLOAD_PREFIX}/"
else:
    STATIC_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{STATIC_UPLOAD_PREFIX}/"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "endpoint_url": AWS_S3_ENDPOINT_URL,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            "location": STATIC_UPLOAD_PREFIX,
            "querystring_auth": AWS_QUERYSTRING_AUTH,
            "file_overwrite": True,
            "object_parameters": {
                "CacheControl": os.getenv(
                    "AWS_STATIC_CACHE_CONTROL",
                    "max-age=31536000, public",
                ),
            },
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.StaffUser"

CORS_ALLOW_ALL_ORIGINS = os.getenv("DJANGO_CORS_ALLOW_ALL_ORIGINS", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CORS_ALLOW_CREDENTIALS = os.getenv("DJANGO_CORS_ALLOW_CREDENTIALS", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_ANON_THROTTLE_RATE", "200/hour"),
        "user": os.getenv("DRF_USER_THROTTLE_RATE", "1000/hour"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Autoshowroom API",
    "DESCRIPTION": (
        "Dealer marketplace API covering authentication, vehicle listings, public feed, "
        "buyer identity, leads, bookings, billing, and platform operations. Successful "
        "responses are wrapped in a `data` envelope by default."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Auth", "description": "Dealer staff login, refresh, invite, and session location workflows."},
        {"name": "Dealers", "description": "Dealer profile, staff, locations, verification, sanctions, and privacy workflows."},
        {"name": "Vehicles", "description": "Dealer listing management, review actions, direct media uploads, and vehicle-scoped chats."},
        {"name": "Marketplace", "description": "Public feed, public vehicle details, dealers, locations, and feed metadata."},
        {"name": "Leads", "description": "Public lead capture and dealer lead management."},
        {"name": "Buyers", "description": "Buyer OTP sessions, profile, saved vehicles, and visits."},
        {"name": "Bookings", "description": "Inspection booking, OTP verification, and dealer appointments."},
        {"name": "Billing", "description": "Dealer billing plans, invoices, checkout, webhooks, and platform billing operations."},
        {"name": "Platform", "description": "Platform users, roles, settings, reports, DSR, sanctions, watchlists, and audit."},
        {"name": "Uploads", "description": "Generic and vehicle-specific presigned upload flows."},
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "60"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/2")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

BUYER_TOKEN_TTL_SECONDS = int(os.getenv("BUYER_TOKEN_TTL_SECONDS", "604800"))
OTP_CODE_TTL_MINUTES = int(os.getenv("OTP_CODE_TTL_MINUTES", "10"))
