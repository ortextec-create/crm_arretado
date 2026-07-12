"""
Management command: listar_candidatos_revenda

Lista produtos ativos do tipo 'fabricado' (default de todo produto pré-existente)
que não têm FichaTecnica vinculada — candidatos prováveis a serem reclassificados
manualmente para 'revenda' (ex: refrigerantes, água), conforme CATALOGO_PRODUTOS.md.

Não faz nenhuma alteração no banco — apenas lista, pra facilitar a varredura manual
na tela de edição do Catálogo.
"""
from django.core.management.base import BaseCommand

from pdv.models import Produto
from fichas.models import FichaTecnica


class Command(BaseCommand):
    help = 'Lista produtos "fabricado" sem ficha técnica vinculada (candidatos a revenda)'

    def handle(self, *args, **options):
        produtos_com_ficha = set(
            FichaTecnica.objects.filter(ativo=True).values_list('produto_pdv_id', flat=True)
        )
        candidatos = (
            Produto.objects.filter(ativo=True, tipo='fabricado')
            .exclude(id__in=produtos_com_ficha)
            .order_by('categoria__ordem', 'nome')
        )

        if not candidatos:
            self.stdout.write(self.style.SUCCESS('Nenhum candidato encontrado.'))
            return

        self.stdout.write(f'{candidatos.count()} candidato(s) a "revenda" (sem ficha técnica):\n')
        for p in candidatos:
            categoria = p.categoria.nome if p.categoria else '— sem categoria —'
            self.stdout.write(f'  #{p.id:>4}  {p.nome:<40}  {categoria}')
