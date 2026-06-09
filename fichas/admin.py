from django.contrib import admin
from .models import MateriaPrima, FichaTecnica, ItemFichaTecnica, ParametrosNegocio, SnapshotPrecos


@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'unidade_compra', 'valor_compra', 'custo_unitario_display', 'ativo')
    search_fields = ('nome',)
    list_filter   = ('ativo', 'unidade_medida')

    @admin.display(description='Custo/un')
    def custo_unitario_display(self, obj):
        return f'R$ {obj.custo_unitario:.5f}'


class ItemFichaTecnicaInline(admin.TabularInline):
    model           = ItemFichaTecnica
    extra           = 0
    fields          = ('materia_prima', 'quantidade', 'custo_proporcional_display')
    readonly_fields = ('custo_proporcional_display',)

    @admin.display(description='Custo proporcional')
    def custo_proporcional_display(self, obj):
        return f'R$ {obj.custo_proporcional:.4f}'


@admin.register(FichaTecnica)
class FichaTecnicaAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'rendimento', 'custo_total_display', 'preco_ideal_display', 'ativo')
    search_fields = ('nome',)
    inlines       = [ItemFichaTecnicaInline]

    @admin.display(description='Custo/un')
    def custo_total_display(self, obj):
        return f'R$ {obj.custo_total_unitario:.3f}'

    @admin.display(description='Preço ideal')
    def preco_ideal_display(self, obj):
        return f'R$ {obj.preco_ideal:.2f}'


@admin.register(ParametrosNegocio)
class ParametrosNegocioAdmin(admin.ModelAdmin):
    list_display = (
        'faturamento_meta', 'despesa_fixa_mensal',
        'despesa_variavel_pct', 'margem_lucro_esperada_pct',
    )


@admin.register(SnapshotPrecos)
class SnapshotPrecosAdmin(admin.ModelAdmin):
    list_display    = ('descricao', 'criado_em', 'revertido')
    list_filter     = ('revertido',)
    readonly_fields = ('criado_em', 'dados')
