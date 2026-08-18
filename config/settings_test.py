"""
Settings de teste — só para rodar `manage.py test` localmente.
O usuário do Postgres em produção não tem permissão de CREATE DATABASE,
então os testes rodam contra SQLite em memória (schema idêntico via migrations).
Arquivo temporário de verificação, não faz parte do deploy.
"""
import tempfile

from .settings import *  # noqa

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# MEDIA_ROOT isolado — testes com FileField/ImageField (ex: ImagemInspiracao,
# ImportacaoNotaFiscal) gravam de verdade no disco, mesmo com banco em memória.
# Sem isso, cada `manage.py test` escreve fixtures no media/ real de produção
# (bug encontrado 18/ago/2026: PermissionError ao subir foto num Orçamento,
# porque um diretório de mídia tinha sido criado por um teste rodado como
# root, ficando sem permissão de escrita pro www-data do Gunicorn).
MEDIA_ROOT = tempfile.mkdtemp(prefix='arretado_test_media_')
