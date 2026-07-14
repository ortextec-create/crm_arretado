"""
Management command: python manage.py alertar_eventos
Roda diariamente (cron). Avisa a equipe interna (telefones cadastrados em
TelefoneAlertaEvento) via WhatsApp sobre:
  1) Eventos com saldo pendente perto da data do evento.
  2) Eventos com entrega (tipo_entrega='entrega_local') se aproximando.
Janelas de dias e intervalo de repetição vêm de ConfiguracaoAlertaEvento.get().
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from eventos.models import (
    Evento, ConfiguracaoAlertaEvento, TelefoneAlertaEvento, AlertaEventoEnviado,
)
from notificacoes.servico import notificar


class Command(BaseCommand):
    help = 'Alerta a equipe (WhatsApp) sobre eventos com pagamento pendente ou entrega próxima'

    def handle(self, *args, **options):
        cfg = ConfiguracaoAlertaEvento.get()
        hoje = timezone.localdate()
        telefones = list(
            TelefoneAlertaEvento.objects.filter(ativo=True).values_list('numero', flat=True)
        )

        if not telefones:
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        total_enviados = 0

        if cfg.ativo_pagamento:
            total_enviados += self._checar_pagamento_pendente(cfg, hoje, telefones)
        else:
            self.stdout.write('Alerta de pagamento pendente desativado na configuração.')

        if cfg.ativo_entrega:
            total_enviados += self._checar_aviso_entrega(cfg, hoje, telefones)
        else:
            self.stdout.write('Alerta de entrega desativado na configuração.')

        self.stdout.write(self.style.SUCCESS(f'Concluído: {total_enviados} alerta(s) enviado(s).'))

    def _deve_enviar(self, evento, tipo, repetir_dias):
        ultimo = evento.alertas_enviados.filter(tipo=tipo).order_by('-enviado_em').first()
        if not ultimo:
            return True
        return (timezone.now() - ultimo.enviado_em).days >= repetir_dias

    def _disparar(self, telefones, mensagem, tipo_notificacao):
        enviado_algum = False
        for fone in telefones:
            if notificar(telefone=fone, mensagem=mensagem, tipo=tipo_notificacao):
                enviado_algum = True
        return enviado_algum

    def _checar_pagamento_pendente(self, cfg, hoje, telefones):
        limite = hoje + timedelta(days=cfg.dias_antes_pagamento)
        qs = (
            Evento.objects
            .exclude(status__in=['cancelado', 'entregue'])
            .annotate(saldo=F('valor_total') - F('sinal_pago'))
            .filter(saldo__gt=0, data_evento__gte=hoje, data_evento__lte=limite)
        )

        enviados = 0
        for evento in qs:
            if not self._deve_enviar(evento, 'pagamento_pendente', cfg.repetir_pagamento_dias):
                continue

            dias_restantes = (evento.data_evento - hoje).days
            mensagem = (
                f'⚠️ Pagamento pendente — Evento {evento.numero} ({evento.nome_cliente_display})\n'
                f'Data do evento: {evento.data_evento.strftime("%d/%m/%Y")} '
                f'(faltam {dias_restantes} dia(s))\n'
                f'Saldo pendente: R$ {evento.saldo:.2f}'
            )
            if self._disparar(telefones, mensagem, 'alerta_pagamento'):
                AlertaEventoEnviado.objects.create(evento=evento, tipo='pagamento_pendente')
                enviados += 1
                self.stdout.write(f'  ✓ Pagamento pendente — {evento.numero}')
            else:
                self.stderr.write(f'  ✗ Pagamento pendente — {evento.numero}: falha no envio')

        return enviados

    def _checar_aviso_entrega(self, cfg, hoje, telefones):
        limite = hoje + timedelta(days=cfg.dias_antes_entrega)
        qs = (
            Evento.objects
            .exclude(status__in=['cancelado', 'entregue'])
            .filter(tipo_entrega='entrega_local', data_evento__gte=hoje, data_evento__lte=limite)
        )

        enviados = 0
        for evento in qs:
            if not self._deve_enviar(evento, 'aviso_entrega', cfg.repetir_entrega_dias):
                continue

            dias_restantes = (evento.data_evento - hoje).days
            local = evento.local.nome if evento.local else (evento.endereco_avulso or 'endereço não informado')
            hora  = evento.hora_evento.strftime('%H:%M') if evento.hora_evento else 'horário não informado'
            mensagem = (
                f'📍 Entrega próxima — Evento {evento.numero} ({evento.nome_cliente_display})\n'
                f'Data: {evento.data_evento.strftime("%d/%m/%Y")} às {hora} '
                f'(faltam {dias_restantes} dia(s))\n'
                f'Local: {local}' + (f' — {evento.bairro_entrega}' if evento.bairro_entrega else '')
            )
            if self._disparar(telefones, mensagem, 'alerta_entrega'):
                AlertaEventoEnviado.objects.create(evento=evento, tipo='aviso_entrega')
                enviados += 1
                self.stdout.write(f'  ✓ Aviso de entrega — {evento.numero}')
            else:
                self.stderr.write(f'  ✗ Aviso de entrega — {evento.numero}: falha no envio')

        return enviados
