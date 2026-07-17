"""
Management command: python manage.py alertar_estoque_baixo
Roda diariamente (cron). Avisa a equipe interna (telefones cadastrados em
TelefoneAlertaEstoque) via WhatsApp sobre insumos/produtos com saldo abaixo
do mínimo configurado. Janela de repetição vem de ConfiguracaoEstoque.get().
"""
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone

from estoque.models import AlertaEstoqueEnviado, ConfiguracaoEstoque, TelefoneAlertaEstoque
from fichas.models import MateriaPrima
from notificacoes.servico import notificar
from pdv.models import Produto


class Command(BaseCommand):
    help = 'Alerta a equipe (WhatsApp) sobre insumos/produtos com estoque abaixo do mínimo'

    def handle(self, *args, **options):
        cfg = ConfiguracaoEstoque.get()

        if not cfg.alerta_whatsapp_ativo:
            self.stdout.write('Alerta de estoque desativado na configuração.')
            return

        telefones = list(
            TelefoneAlertaEstoque.objects.filter(ativo=True).values_list('numero', flat=True)
        )
        if not telefones:
            self.stdout.write('Nenhum telefone de alerta cadastrado/ativo — nada a fazer.')
            return

        total_enviados = 0
        total_enviados += self._checar_materias_primas(cfg, telefones)
        total_enviados += self._checar_produtos(cfg, telefones)

        self.stdout.write(self.style.SUCCESS(f'Concluído: {total_enviados} alerta(s) enviado(s).'))

    def _deve_enviar(self, item, tipo, repetir_diariamente):
        filtro = {'materia_prima': item} if tipo == 'materia_prima' else {'produto': item}
        ultimo = AlertaEstoqueEnviado.objects.filter(tipo=tipo, **filtro).order_by('-enviado_em').first()
        if not ultimo:
            return True
        if not repetir_diariamente:
            return False
        return timezone.now().date() > ultimo.enviado_em.date()

    def _disparar(self, telefones, mensagem):
        enviado_algum = False
        for fone in telefones:
            if notificar(telefone=fone, mensagem=mensagem, tipo='alerta_estoque_baixo'):
                enviado_algum = True
        return enviado_algum

    def _checar_materias_primas(self, cfg, telefones):
        qs = MateriaPrima.objects.filter(
            estoque_minimo__gt=0, quantidade_estoque__lt=F('estoque_minimo'), ativo=True,
        )
        enviados = 0
        for materia in qs:
            if not self._deve_enviar(materia, 'materia_prima', cfg.alerta_repetir_diariamente):
                continue
            mensagem = (
                f'⚠️ Estoque baixo — Insumo "{materia.nome}"\n'
                f'Saldo atual: {materia.quantidade_estoque} {materia.get_unidade_medida_display()} '
                f'(mínimo: {materia.estoque_minimo})'
            )
            if self._disparar(telefones, mensagem):
                AlertaEstoqueEnviado.objects.create(materia_prima=materia, tipo='materia_prima')
                enviados += 1
                self.stdout.write(f'  ✓ Insumo — {materia.nome}')
            else:
                self.stderr.write(f'  ✗ Insumo — {materia.nome}: falha no envio')
        return enviados

    def _checar_produtos(self, cfg, telefones):
        qs = Produto.objects.filter(
            estoque_minimo__gt=0, quantidade_estoque__lt=F('estoque_minimo'), ativo=True,
        ).exclude(tipo='kit')
        enviados = 0
        for produto in qs:
            if not self._deve_enviar(produto, 'produto', cfg.alerta_repetir_diariamente):
                continue
            mensagem = (
                f'⚠️ Estoque baixo — Produto "{produto.nome}"\n'
                f'Saldo atual: {produto.quantidade_estoque} un. (mínimo: {produto.estoque_minimo})'
            )
            if self._disparar(telefones, mensagem):
                AlertaEstoqueEnviado.objects.create(produto=produto, tipo='produto')
                enviados += 1
                self.stdout.write(f'  ✓ Produto — {produto.nome}')
            else:
                self.stderr.write(f'  ✗ Produto — {produto.nome}: falha no envio')
        return enviados
