import subprocess
from functools import lru_cache

from django.conf import settings


def _git(*args):
    try:
        return subprocess.run(
            ['git', *args], cwd=settings.BASE_DIR, capture_output=True,
            text=True, timeout=5, check=True,
        ).stdout.strip()
    except Exception:
        return ''


@lru_cache(maxsize=1)
def obter_versao():
    """
    Versão da aplicação, sempre derivada do Git — nunca mantida à mão em arquivo/
    settings (ver CLAUDE.md, "Versão do Sistema"). Cacheada por processo: o
    resultado só muda depois de um `git pull` + tag + restart do Gunicorn
    (checklist de deploy), então recalcular a cada request seria desperdício —
    cada worker calcula uma vez, na primeira chamada, e mantém pro resto da vida
    do processo.
    """
    return {
        'versao': _git('describe', '--tags', '--always', '--dirty') or 'desconhecida',
        'commit': _git('rev-parse', '--short', 'HEAD'),
        'commit_data': _git('log', '-1', '--format=%cI'),
        'branch': _git('rev-parse', '--abbrev-ref', 'HEAD'),
    }
