"""
Management command: python manage.py verificar_backup
Roda diariamente (cron), depois de fazer_backup. Checa se o backup mais
recente existe, está atualizado e não está vazio/corrompido — em caso de
problema, alerta a equipe via WhatsApp (TelefoneAlertaBackup).

Decisão consciente: sem controle de repetição (AlertaBackupEnviado) — enquanto
o backup estiver quebrado, o alerta repete todo dia de propósito.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from manutencao.models import ConfiguracaoBackup, TelefoneAlertaBackup
from notificacoes.servico import notificar

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Checa idade/integridade do backup mais recente e alerta a equipe via WhatsApp em caso de problema'

    def handle(self, *args, **options):
        cfg = ConfiguracaoBackup.get()
        problema = self._diagnosticar(cfg)

        if not problema:
            self.stdout.write(self.style.SUCCESS('Backup ok — sem problemas encontrados.'))
            return

        self.stderr.write(self.style.ERROR(problema))
        self._alertar(problema)

    def _diagnosticar(self, cfg):
        pasta_db = Path(cfg.pasta_backup_db)
        dumps = sorted(pasta_db.glob('crm_db_*.dump'), key=lambda p: p.stat().st_mtime, reverse=True)

        if not dumps:
            return 'Nenhum backup encontrado em ' + str(pasta_db)

        mais_recente = dumps[0]
        mtime = datetime.fromtimestamp(mais_recente.stat().st_mtime, tz=timezone.get_current_timezone())

        idade = timezone.now() - mtime
        limite = timedelta(hours=cfg.horas_limite_alerta)
        if idade > limite:
            horas = idade.total_seconds() / 3600
            return (
                f'Backup desatualizado: "{mais_recente.name}" tem {horas:.1f}h '
                f'(limite: {cfg.horas_limite_alerta}h)'
            )

        tamanho_kb = mais_recente.stat().st_size / 1024
        if tamanho_kb < cfg.tamanho_minimo_kb:
            return (
                f'Backup suspeito de vazio/corrompido: "{mais_recente.name}" tem {tamanho_kb:.1f} KB '
                f'(mínimo: {cfg.tamanho_minimo_kb} KB)'
            )

        return None

    def _alertar(self, problema):
        telefones = list(
            TelefoneAlertaBackup.objects.filter(ativo=True).values_list('numero', flat=True)
        )
        if not telefones:
            logger.warning('Backup com problema mas nenhum TelefoneAlertaBackup ativo cadastrado.')
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        mensagem = (
            f'🚨 Problema no backup — {timezone.now().strftime("%d/%m/%Y %H:%M")}\n{problema}'
        )
        for fone in telefones:
            notificar(telefone=fone, mensagem=mensagem, tipo='backup')
        self.stdout.write(f'Alerta enviado para {len(telefones)} telefone(s).')
