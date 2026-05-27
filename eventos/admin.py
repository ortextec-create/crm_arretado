from django.contrib import admin
from .models import LocalEvento, Evento, ItemEvento


@admin.register(LocalEvento)
class LocalEventoAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'bairro', 'cidade', 'ativo')
    list_filter   = ('ativo', 'cidade')
    search_fields = ('nome', 'bairro', 'endereco')
    ordering      = ('nome',)


class ItemEventoInline(admin.TabularInline):
    model         = ItemEvento
    extra         = 0
    fields        = ('nome', 'quantidade', 'preco_unit', 'preco_total', 'observacao')
    readonly_fields = ('preco_total',)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display    = ('numero', 'status', 'tipo_evento', 'data_evento',
                       'hora_evento', 'nome_cliente_display', 'valor_total')
    list_filter     = ('status', 'tipo_evento', 'tipo_entrega')
    search_fields   = ('numero', 'cliente_nome', 'cliente__nome')
    ordering        = ('data_evento', 'hora_evento')
    inlines         = [ItemEventoInline]
    readonly_fields = ('subtotal', 'valor_total', 'saldo_restante', 'criado_em', 'atualizado_em')

    fieldsets = (
        ('Identificação', {
            'fields': ('numero', 'status', 'tipo_evento', 'data_evento', 'hora_evento'),
        }),
        ('Cliente', {
            'fields': ('cliente', 'cliente_nome', 'cliente_telefone'),
        }),
        ('Entrega', {
            'fields': ('tipo_entrega', 'local', 'endereco_avulso'),
        }),
        ('Financeiro', {
            'fields': ('subtotal', 'desconto', 'valor_total', 'sinal_pago', 'saldo_restante'),
        }),
        ('Observações', {
            'fields': ('observacoes',),
        }),
        ('Datas', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',),
        }),
    )
