from django.contrib import admin
from django.utils.html import format_html
from .models import ConfiguracaoIFood, PedidoIFood, ItemPedidoIFood, EventoPollingIFood


@admin.register(ConfiguracaoIFood)
class ConfiguracaoIFoodAdmin(admin.ModelAdmin):
    list_display  = ['merchant_id', 'polling_ativo', 'token_badge', 'ultimo_polling']
    readonly_fields = ['access_token', 'token_expira_em', 'ultimo_polling', 'criado_em', 'atualizado_em']

    def token_badge(self, obj):
        if obj.token_valido:
            return format_html('<span style="color:green">✓ Válido</span>')
        return format_html('<span style="color:red">✗ Expirado</span>')
    token_badge.short_description = 'Token'


class ItemInline(admin.TabularInline):
    model  = ItemPedidoIFood
    extra  = 0
    fields = ['nome', 'quantidade', 'preco_unit', 'preco_total', 'observacao']
    readonly_fields = fields


@admin.register(PedidoIFood)
class PedidoIFoodAdmin(admin.ModelAdmin):
    list_display  = ['display_id', 'cliente_nome', 'status_badge', 'order_type', 'total_valor', 'ifood_criado_em']
    list_filter   = ['status', 'order_type', 'ifood_criado_em']
    search_fields = ['display_id', 'ifood_order_id', 'cliente_nome', 'cliente_telefone']
    readonly_fields = ['ifood_order_id', 'payload_raw', 'criado_em', 'atualizado_em', 'ifood_criado_em']
    inlines = [ItemInline]

    def status_badge(self, obj):
        colors = {
            'PLACED': '#F59E0B', 'CONFIRMED': '#3B82F6',
            'PREPARATION_STARTED': '#8B5CF6', 'READY_TO_PICKUP': '#06B6D4',
            'DISPATCHED': '#6366F1', 'CONCLUDED': '#22C55E',
            'CANCELLATION_REQUESTED': '#F97316', 'CANCELLED': '#EF4444',
        }
        color = colors.get(obj.status, '#9CA3AF')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(EventoPollingIFood)
class EventoPollingAdmin(admin.ModelAdmin):
    list_display = ['full_code', 'order_id', 'acknowledged', 'processado', 'ifood_criado_em']
    list_filter  = ['code', 'acknowledged', 'processado']
    readonly_fields = [f.name for f in EventoPollingIFood._meta.fields]
