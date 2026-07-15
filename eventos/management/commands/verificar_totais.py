"""
Management command: verificar_totais

Compara o subtotal/valor_total (Orcamento, Evento) e subtotal/total (PedidoPDV)
salvos no banco com o valor recalculado a partir dos itens atuais — detecta
registros afetados pelo bug de cache stale do prefetch_related (corrigido em
adicionar_item/remover_item/editar_item de OrcamentoViewSet/EventoViewSet e
adicionar_item/remover_item de PedidoPDVViewSet, ver CLAUDE.md).

Por padrão só LISTA as divergências — não altera nada no banco (o
recalcular_totais() de cada registro roda dentro de uma transação que é
sempre desfeita nesse modo). Rodar com --aplicar pra de fato persistir a
correção.

Uso:
  python manage.py verificar_totais              # só lista
  python manage.py verificar_totais --aplicar     # lista e corrige
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from eventos.models import Orcamento, Evento
from pdv.models import PedidoPDV


class Command(BaseCommand):
    help = 'Lista (e, com --aplicar, corrige) Orçamentos/Eventos/Pedidos PDV com total divergente da soma dos itens atuais'

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Aplica a correção (recalcula e salva). Sem essa flag, só lista as divergências.',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']

        total_divergencias = 0
        total_divergencias += self._verificar(Orcamento.objects.all(), 'Orçamento', 'numero', 'valor_total', aplicar)
        total_divergencias += self._verificar(Evento.objects.all(), 'Evento', 'numero', 'valor_total', aplicar)
        total_divergencias += self._verificar(PedidoPDV.objects.all(), 'Pedido PDV', 'numero', 'total', aplicar)

        self.stdout.write('')
        if total_divergencias == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma divergência encontrada.'))
        elif aplicar:
            self.stdout.write(self.style.SUCCESS(f'{total_divergencias} registro(s) corrigido(s).'))
        else:
            self.stdout.write(self.style.WARNING(
                f'{total_divergencias} registro(s) com divergência — nada foi alterado. '
                f'Rode "python manage.py verificar_totais --aplicar" pra corrigir.'
            ))

    def _verificar(self, queryset, label, campo_numero, campo_total, aplicar):
        total = queryset.count()
        encontrados = 0

        for obj in queryset.order_by('id').iterator():
            antes = getattr(obj, campo_total)
            with transaction.atomic():
                obj.recalcular_totais()
                depois = getattr(obj, campo_total)
                if not aplicar:
                    # desfaz o save() feito por recalcular_totais() — modo só-listagem
                    transaction.set_rollback(True)

            if antes != depois:
                encontrados += 1
                numero = getattr(obj, campo_numero, None) or obj.pk
                acao = 'corrigido' if aplicar else 'divergente'
                self.stdout.write(
                    f'  [{acao}] {label} {numero} (#{obj.pk}): '
                    f'{campo_total} salvo=R$ {antes}  →  correto=R$ {depois}'
                )

        self.stdout.write(f'{label}: {total} registro(s) verificado(s), {encontrados} divergência(s)\n')
        return encontrados
