from django.contrib import admin
from .models import (
    CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV,
    ItemKit, FaixaPreco, DadosFiscaisProduto,
)


@admin.register(CategoriaProduto)
class CategoriaProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem')
    ordering     = ('ordem', 'nome')


class ItemKitInline(admin.TabularInline):
    model = ItemKit
    fk_name = 'kit'
    extra = 0


class FaixaPrecoInline(admin.TabularInline):
    model = FaixaPreco
    extra = 0


class DadosFiscaisProdutoInline(admin.StackedInline):
    model = DadosFiscaisProduto
    extra = 0


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'categoria', 'tipo', 'preco', 'ativo')
    list_filter   = ('ativo', 'categoria', 'tipo')
    search_fields = ('nome',)
    ordering      = ('categoria__ordem', 'nome')
    inlines       = [FaixaPrecoInline, ItemKitInline, DadosFiscaisProdutoInline]


class ItemPedidoPDVInline(admin.TabularInline):
    model  = ItemPedidoPDV
    extra  = 0
    fields = ('nome', 'quantidade', 'preco_unit', 'preco_total', 'observacao')
    readonly_fields = ('preco_total',)


@admin.register(PedidoPDV)
class PedidoPDVAdmin(admin.ModelAdmin):
    list_display  = ('numero', 'status', 'tipo', 'total', 'cliente_nome', 'criado_em')
    list_filter   = ('status', 'tipo', 'pagamento')
    search_fields = ('numero', 'cliente_nome', 'cliente_telefone')
    ordering      = ('-criado_em',)
    inlines       = [ItemPedidoPDVInline]
    readonly_fields = ('subtotal', 'total', 'criado_em', 'atualizado_em')
