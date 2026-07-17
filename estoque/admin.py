from django.contrib import admin

from .models import (
    AlertaEstoqueEnviado,
    ConfiguracaoEstoque,
    MovimentoEstoque,
    Producao,
    TelefoneAlertaEstoque,
)


@admin.register(MovimentoEstoque)
class MovimentoEstoqueAdmin(admin.ModelAdmin):
    list_display = ['id', 'tipo_movimento', 'materia_prima', 'produto', 'quantidade',
                     'saldo_posterior', 'origem_tipo', 'origem_id', 'criado_em']
    list_filter = ['tipo_movimento', 'origem_tipo']
    readonly_fields = [f.name for f in MovimentoEstoque._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Producao)
class ProducaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'ficha_tecnica', 'quantidade_produzida', 'criado_por', 'criado_em']


@admin.register(ConfiguracaoEstoque)
class ConfiguracaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ['estoque_minimo_padrao', 'alerta_whatsapp_ativo', 'alerta_repetir_diariamente']


@admin.register(TelefoneAlertaEstoque)
class TelefoneAlertaEstoqueAdmin(admin.ModelAdmin):
    list_display = ['nome', 'numero', 'ativo']


@admin.register(AlertaEstoqueEnviado)
class AlertaEstoqueEnviadoAdmin(admin.ModelAdmin):
    list_display = ['materia_prima', 'produto', 'tipo', 'enviado_em']
