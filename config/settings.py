from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'ifood',
    'clientes',
    'pedidos',
    'pdv',
    'eventos',
    'usuarios',
    'notificacoes',
    'fichas',
    'relatorios',
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
        'DIRS': [],
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

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', ''),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Integrações externas (lidas pelo código da Fase 2)
IFOOD_CLIENT_ID = os.getenv('IFOOD_CLIENT_ID', '')
IFOOD_CLIENT_SECRET = os.getenv('IFOOD_CLIENT_SECRET', '')
IFOOD_MERCHANT_ID = os.getenv('IFOOD_MERCHANT_ID', '')

ANOTAAI_TOKEN = os.getenv('ANOTAAI_TOKEN', '')
ANOTAAI_STORE_ID = os.getenv('ANOTAAI_STORE_ID', '')

EVOLUTION_API_URL  = os.getenv('EVOLUTION_API_URL', '')
EVOLUTION_API_KEY  = os.getenv('EVOLUTION_API_KEY', '')
EVOLUTION_INSTANCE = os.getenv('EVOLUTION_INSTANCE', 'arretado')

# WhatsApp — Twilio (desativado)
TWILIO_ACCOUNT_SID    = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN     = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_FROM  = os.getenv('TWILIO_WHATSAPP_FROM', '')
TWILIO_CONTENT_SID    = os.getenv('TWILIO_CONTENT_SID', '')

# WhatsApp — Z-API
ZAPI_INSTANCE_ID  = os.getenv('ZAPI_INSTANCE_ID', '')
ZAPI_TOKEN        = os.getenv('ZAPI_TOKEN', '')
ZAPI_CLIENT_TOKEN = os.getenv('ZAPI_CLIENT_TOKEN', '')