"""
Django settings for the Built To Work event trailer platform.

This project is intentionally split into small apps that mirror the
sections of the platform spec (event-trailer-platform-spec.md):

    core          - custom User model, roles/scope (spec Section 2)
    participants  - permanent participant identity, intake, attendance,
                    on-site flags/notes (spec Sections 4, 6)
    stations      - station results from the kiosk, game, and simulators
                    (spec Section 5)
    formbuilder   - the configurable form/question builder used by intake
                    and the kiosk test, with event-type presets and
                    versioning (spec Section 14a)
    events        - event details, housing, daily staffing needs, expenses,
                    and the finalized cost-per-lead report (spec Sections
                    10-11)
    staffing      - staff records, availability requests, assignments,
                    check-in, work reports, pay roles, mileage bands,
                    payroll periods, paystubs, adjustments (spec Section 10)
    customers     - customers, agreements, plans, and exclusivity
                    (spec Section 8)
    opportunities - HubSpot-linked opportunities and participant interest
                    (spec Section 9)

Two settings this project cares about that a generic Django project
wouldn't:

  - This is meant to run BOTH on the trailer server (local-only,
    offline-first) and in the cloud (spec Section 3). The database is
    swappable via the DATABASE_URL-style env vars below so the same
    codebase runs on SQLite for local trailer use or Postgres in the
    cloud, without code changes.
  - AUTH_USER_MODEL is a custom user (apps.core.User) from the start,
    because retrofitting a custom user model after the fact is painful
    in Django. It carries the access role from spec Section 2 (admin,
    event_lead, staff, customer).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Set DJANGO_SECRET_KEY in the environment for any real deployment.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'dev-only-insecure-key-change-me',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'apps.core',
    'apps.participants',
    'apps.stations',
    'apps.formbuilder',
    'apps.events',
    'apps.staffing',
    'apps.customers',
    'apps.opportunities',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- Database ---------------------------------------------------------
# Local/trailer use: SQLite, zero setup, works fully offline (spec
# Section 7). Cloud use: set DJANGO_DB_ENGINE=postgres plus the usual
# POSTGRES_* env vars, and this switches with no code changes.
if os.environ.get('DJANGO_DB_ENGINE') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'btw_platform'),
            'USER': os.environ.get('POSTGRES_USER', 'btw_platform'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'America/New_York')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
