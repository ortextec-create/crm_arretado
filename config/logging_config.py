"""
Configuração de logging (ver LOGGING.md).

`montar_logging()` é pura: não cria diretório, só checa permissão. Falha de
configuração de log nunca pode derrubar o boot do Django — na dúvida, cai
para console.

Rotação NÃO é feita aqui: vários processos (Gunicorn, polling, crons) escrevem
nos mesmos arquivos, então `WatchedFileHandler` + `logrotate` do sistema.
"""
import os
import sys

FORMATO = '%(asctime)s %(levelname)s [pid %(process)d] %(name)s: %(message)s'
FORMATO_DATA = '%Y-%m-%d %H:%M:%S %z'
NIVEIS_VALIDOS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}


def montar_logging(log_dir, nivel='INFO'):
    nivel = (nivel or 'INFO').upper()
    if nivel not in NIVEIS_VALIDOS:
        nivel = 'INFO'

    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'padrao',
            'stream': 'ext://sys.stderr',
        },
    }
    handlers_root = ['console']

    if log_dir:
        if os.path.isdir(log_dir) and os.access(log_dir, os.W_OK | os.X_OK):
            handlers['arquivo'] = {
                'class': 'logging.handlers.WatchedFileHandler',
                'formatter': 'padrao',
                'filename': os.path.join(log_dir, 'arretado.log'),
                'encoding': 'utf-8',
            }
            handlers['arquivo_erros'] = {
                'class': 'logging.handlers.WatchedFileHandler',
                'formatter': 'padrao',
                'filename': os.path.join(log_dir, 'arretado-erros.log'),
                'encoding': 'utf-8',
                'level': 'ERROR',
            }
            handlers_root += ['arquivo', 'arquivo_erros']
        else:
            print(
                f'[logging] LOG_DIR={log_dir!r} inexistente ou sem permissão de '
                f'escrita — logando só no console.',
                file=sys.stderr,
            )

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'padrao': {'format': FORMATO, 'datefmt': FORMATO_DATA},
        },
        'handlers': handlers,
        'root': {'handlers': handlers_root, 'level': nivel},
        'loggers': {
            'django': {'level': 'INFO'},
            'django.db.backends': {'level': 'WARNING'},
            'urllib3': {'level': 'WARNING'},
        },
    }
