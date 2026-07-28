"""
Management command: python manage.py fazer_backup
Roda diariamente (cron). Faz pg_dump do banco + tar.gz da pasta media/,
rotaciona backups locais antigos e envia (opcional) pro Google Drive via rclone.
Nunca notifica por WhatsApp — quem alerta é o verificar_backup, separadamente.
"""
import logging
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from manutencao.models import ConfiguracaoBackup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backup do banco PostgreSQL (pg_dump) e da pasta media/ (tarfile), com envio opcional pro Drive via rclone'

    def handle(self, *args, **options):
        cfg = ConfiguracaoBackup.get()
        if not cfg.ativo:
            self.stdout.write('Backup desativado na configuração — nada a fazer.')
            return

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        pasta_db = Path(cfg.pasta_backup_db)
        pasta_media = Path(cfg.pasta_backup_media)
        pasta_db.mkdir(parents=True, exist_ok=True)
        pasta_media.mkdir(parents=True, exist_ok=True)

        dump_path = self._fazer_dump_db(pasta_db, timestamp)
        media_path = self._compactar_media(pasta_media, timestamp)

        self._rotacionar_local(pasta_db, 'crm_db_*.dump', cfg.retencao_local_dias)
        self._rotacionar_local(pasta_media, 'media_*.tar.gz', cfg.retencao_local_dias)

        envio_ok = False
        if cfg.envio_externo_ativo:
            envio_ok = self._enviar_externo(cfg, dump_path, media_path)

        self.stdout.write(self.style.SUCCESS(
            f'Backup concluído — db: {dump_path.name} ({dump_path.stat().st_size // 1024} KB), '
            f'media: {media_path.name} ({media_path.stat().st_size // 1024} KB), '
            f'envio externo: {"ok" if envio_ok else "não realizado"}'
        ))

    def _fazer_dump_db(self, pasta_db, timestamp):
        db = settings.DATABASES['default']
        dump_path = pasta_db / f'crm_db_{timestamp}.dump'

        comando = [
            'pg_dump', '-Fc',
            '-h', db['HOST'] or 'localhost',
            '-p', str(db['PORT'] or 5432),
            '-U', db['USER'],
            '-d', db['NAME'],
            '-f', str(dump_path),
        ]
        env = os.environ.copy()
        env['PGPASSWORD'] = db['PASSWORD']

        resultado = subprocess.run(comando, env=env, capture_output=True, text=True)
        if resultado.returncode != 0:
            logger.error('pg_dump falhou: %s', resultado.stderr)
            raise CommandError(f'pg_dump falhou (código {resultado.returncode}): {resultado.stderr}')

        return dump_path

    def _compactar_media(self, pasta_media, timestamp):
        media_path = pasta_media / f'media_{timestamp}.tar.gz'
        with tarfile.open(media_path, 'w:gz') as tar:
            tar.add(settings.MEDIA_ROOT, arcname='media')
        return media_path

    def _rotacionar_local(self, pasta, padrao, retencao_dias):
        limite = timezone.now() - timedelta(days=retencao_dias)
        tz = timezone.get_current_timezone()
        for arquivo in pasta.glob(padrao):
            mtime = datetime.fromtimestamp(arquivo.stat().st_mtime, tz=tz)
            if mtime < limite:
                arquivo.unlink()
                self.stdout.write(f'  Rotação local: removido {arquivo.name}')

    def _enviar_externo(self, cfg, dump_path, media_path):
        if not shutil.which('rclone'):
            logger.warning('rclone não encontrado no sistema — envio externo pulado.')
            return False

        remotes = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True)
        if f'{cfg.rclone_remote}:' not in remotes.stdout:
            logger.warning('Remote "%s" não configurado no rclone — envio externo pulado.', cfg.rclone_remote)
            return False

        ok = True
        for origem, subpasta in [(dump_path, 'db'), (media_path, 'media')]:
            destino = f'{cfg.rclone_remote}:{cfg.rclone_pasta_remota}/{subpasta}/'
            resultado = subprocess.run(['rclone', 'copy', str(origem), destino], capture_output=True, text=True)
            if resultado.returncode != 0:
                logger.warning('rclone copy falhou (%s -> %s): %s', origem, destino, resultado.stderr)
                ok = False

        for subpasta in ['db', 'media']:
            destino = f'{cfg.rclone_remote}:{cfg.rclone_pasta_remota}/{subpasta}/'
            resultado = subprocess.run(
                ['rclone', 'delete', '--min-age', f'{cfg.retencao_remota_dias}d', destino],
                capture_output=True, text=True,
            )
            if resultado.returncode != 0:
                logger.warning('rclone delete (rotação remota) falhou em %s: %s', destino, resultado.stderr)
                ok = False

        return ok
