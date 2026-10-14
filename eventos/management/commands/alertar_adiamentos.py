"""
Management command: python manage.py alertar_adiamentos [--dry-run]
Roda diariamente (cron 08:45). Avisa a EQUIPE (TelefoneAlertaEvento) sobre
eventos adiados — follow-up, limite próximo e limite vencido (ver ADIAMENTO.md).
Nunca fala com o cliente e nunca encerra um adiamento sozinho.

No máximo UM alerta por evento por dia: o mais grave (vencido > limite > contato).
Repetição controlada por AlertaEventoEnviado + repetir_adiamento_dias.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from eventos.models import (
    AdiamentoEvento, AlertaEventoEnviado, ConfiguracaoAlertaEvento, TelefoneAlertaEvento,
)
from notificacoes.servico import notificar


def decidir_alerta(adiamento, cfg, hoje):
    """(tipo, mensagem) do alerta mais grave aplicável hoje, ou None. Função pura."""
    evento = adiamento.evento
    nome = evento.nome_cliente_display
    dias_limite = (adiamento.limite - hoje).days
    if dias_limite < 0:
        return 'adiamento_vencido', (
            f'🔴 Limite de adiamento vencido — {evento.numero} ({nome}) · decidir: prorrogar ou encerrar'
        )
    if dias_limite <= cfg.dias_antes_limite_adiamento:
        return 'adiamento_limite', (
            f'⚠️ Evento adiado chegando ao limite — {evento.numero} ({nome}) · '
            f'limite {adiamento.limite.strftime("%d/%m/%Y")} ({dias_limite} dias)'
        )
    if adiamento.retomar_contato_em and adiamento.retomar_contato_em <= hoje:
        return 'adiamento_contato', (
            f'⏸️ Follow-up de evento adiado — {evento.numero} ({nome}) · '
            f'adiado em {adiamento.adiado_em.strftime("%d/%m/%Y")} · '
            f'limite {adiamento.limite.strftime("%d/%m/%Y")}'
        )
    return None


class Command(BaseCommand):
    help = 'Alerta a equipe (WhatsApp) sobre eventos adiados: follow-up, limite próximo e limite vencido'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Só lista o que seria enviado')

    def handle(self, *args, **options):
        dry = options['dry_run']
        cfg = ConfiguracaoAlertaEvento.get()
        hoje = timezone.localdate()

        if not cfg.ativo_adiamento:
            self.stdout.write('Alerta de adiamento desativado na configuração.')
            return
        telefones = list(TelefoneAlertaEvento.objects.filter(ativo=True).values_list('numero', flat=True))
        if not telefones:
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        enviados = 0
        vigentes = AdiamentoEvento.objects.filter(encerrado_em__isnull=True).select_related('evento', 'evento__cliente')
        for adiamento in vigentes:
            evento = adiamento.evento
            try:
                decisao = decidir_alerta(adiamento, cfg, hoje)
                if not decisao:
                    continue
                tipo, mensagem = decisao
                ultimo = evento.alertas_enviados.filter(tipo=tipo).order_by('-enviado_em').first()
                if ultimo and (timezone.now() - ultimo.enviado_em).days < cfg.repetir_adiamento_dias:
                    continue
                if dry:
                    self.stdout.write(f'  [dry-run] {tipo} — {mensagem}')
                    continue
                enviou = False
                for fone in telefones:
                    if notificar(telefone=fone, mensagem=mensagem, tipo='alerta_adiamento'):
                        enviou = True
                if enviou:
                    AlertaEventoEnviado.objects.create(evento=evento, tipo=tipo)
                    enviados += 1
                    self.stdout.write(f'  ✓ {tipo} — {evento.numero}')
                else:
                    self.stderr.write(f'  ✗ {tipo} — {evento.numero}: falha no envio')
            except Exception:
                import logging
                logging.getLogger(__name__).exception('alertar_adiamentos: falha no evento %s', evento.numero)

        self.stdout.write(self.style.SUCCESS(f'Concluído: {enviados} alerta(s) enviado(s).'))
