from django.contrib import admin
from .models import PedidoUnificado


@admin.register(PedidoUnificado)
class PedidoUnificadoAdmin(admin.ModelAdmin):
    list_display  = ['canal_badge', 'numero', 'cliente_nome', 'total_fmt', 'status', 'tipo', 'pedido_em']
    list_filter   = ['canal', 'status', 'tipo', 'pedido_em']
    search_fields = ['numero', 'cliente_nome', 'cliente_telefone', 'cliente__nome']
    readonly_fields = [
        'canal', 'origem_id', 'numero', 'status_original',
        'itens_snapshot', 'endereco_entrega',
        'sincronizado_em', 'criado_em',
    ]
    ordering = ['-pedido_em']

    fieldsets = (
        ('Origem', {
            'fields': ('canal', 'origem_id', 'numero', 'status', 'status_original', 'tipo'),
        }),
        ('Cliente', {
            'fields': ('cliente', 'cliente_nome', 'cliente_telefone'),
        }),
        ('Financeiro', {
            'fields': ('subtotal', 'taxa_entrega', 'desconto', 'total', 'pagamento'),
        }),
        ('Detalhes', {
            'fields': ('itens_snapshot', 'endereco_entrega'),
            'classes': ('collapse',),
        }),
        ('Auditoria', {
            'fields': ('pedido_em', 'sincronizado_em', 'criado_em'),
            'classes': ('collapse',),
        }),
    )

    def canal_badge(self, obj):
        from django.utils.html import format_html
        cores = {'ifood': '#EA580C', 'anotaai': '#7C3AED', 'pdv': '#0EA5E9'}
        cor   = cores.get(obj.canal, '#9CA3AF')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            cor, obj.get_canal_display(),
        )
    canal_badge.short_description = 'Canal'

    def total_fmt(self, obj):
        return f'R$ {obj.total:.2f}'
    total_fmt.short_description = 'Total'
