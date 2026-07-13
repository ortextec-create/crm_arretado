"""
Settings de teste — só para rodar `manage.py test` localmente.
O usuário do Postgres em produção não tem permissão de CREATE DATABASE,
então os testes rodam contra SQLite em memória (schema idêntico via migrations).
Arquivo temporário de verificação, não faz parte do deploy.
"""
from .settings import *  # noqa

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
