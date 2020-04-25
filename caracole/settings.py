#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Django settings for floreal project.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
from os import environ as E
import django


BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = E['DJANGO_SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = E.get("DEBUG", "false").lower() == 'true'
ALLOWED_HOSTS = ['localhost', E['PUBLIC_HOST']]

EMAIL_USE_TLS = True
EMAIL_HOST = E['SMTP_HOST']
EMAIL_PORT = int(E['SMTP_PORT'])
EMAIL_HOST_USER = E['SMTP_USER']
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = E['SMTP_PASSWORD']
EMAIL_SUBJECT_PREFIX = '[Circuits Courts Civam] '

# longusernameandemail settings
MAX_USERNAME_LENGTH = 128
MAX_EMAIL_LENGTH = 128
REQUIRE_UNIQUE_EMAIL = False

# Application definitions
DELIVERY_ARCHIVE_DIR = os.path.join(BASE_DIR, "delivery_archive")

if not os.path.isdir(DELIVERY_ARCHIVE_DIR):
    os.makedirs(DELIVERY_ARCHIVE_DIR)


INSTALLED_APPS = (
    'floreal',  # Before auth, so that app's password management templates take precedence
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'impersonate',
    'registration',  # WARNING that's django-registration-redux, not django-registration!
    'django_extensions',
)



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'impersonate.middleware.ImpersonateMiddleware'
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages'
            ],
            'debug': True,
            'string_if_invalid': "[[[Invalid template variable %s]]]"
        }
    }
]

ROOT_URLCONF = 'floreal.urls'

WSGI_APPLICATION = 'caracole.wsgi.application'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": E["POSTGRES_DBNAME"],
        "USER": E["POSTGRES_USER"],
        "PASSWORD": E["POSTGRES_PASSWORD"],
        "HOST": E["POSTGRES_HOST"],
        "PORT": int(E["POSTGRES_PORT"]),
    } if E.get("POSTGRES_DBNAME") else {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': E.get("SQLITE3_DBNAME", BASE_DIR + '/database.sqlite3')
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_L10N = False
USE_TZ = True

LOGIN_URL = "/accounts/login"
LOGIN_REDIRECT_URL = "/"

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "floreal", "static"),
)
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

if not os.path.isdir(MEDIA_ROOT):
    os.makedirs(MEDIA_ROOT)

AUTHENTICATION_BACKENDS = ('django.contrib.auth.backends.ModelBackend',)

if False:
    # Enables real-time SQL logs
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            'django.db.backends': {
                'handlers': ['console'],
                'level': 'DEBUG',
                'propagate': True,
            },
        },
    }