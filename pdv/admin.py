from django.contrib import admin
from .models import CategoriaProduto, Produto, PedidoPDV, ItemPedidoPDV


@admin.register(CategoriaProduto)
class CategoriaProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ordem')
    ordering     = ('ordem', 'nome')


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'categoria', 'preco', 'ativo')
    list_filter   = ('ativo', 'categoria')
    search_fields = ('nome',)
    ordering      = ('categoria__ordem', 'nome')


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
