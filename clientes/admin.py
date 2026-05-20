from django.contrib import admin
from django.utils.html import format_html
from .models import Cliente, Endereco, TagCliente


class EnderecoInline(admin.TabularInline):
    model = Endereco
    extra = 0
    fields = ['tipo', 'apelido', 'logradouro', 'numero', 'bairro', 'cidade', 'estado', 'principal']


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'telefone_principal', 'email', 'status_badge', 'integracoes', 'criado_em']
    list_filter = ['status', 'sexo', 'criado_em']
    search_fields = ['nome', 'cpf', 'email', 'telefone_principal']
    inlines = [EnderecoInline]
    readonly_fields = ['criado_em', 'atualizado_em']
    fieldsets = (
        ('Dados Pessoais', {
            'fields': ('nome', 'cpf', 'email', 'data_nascimento', 'sexo')
        }),
        ('Contato', {
            'fields': ('telefone_principal', 'telefone_secundario')
        }),
        ('Controle', {
            'fields': ('status', 'observacoes')
        }),
        ('Integrações Externas', {
            'fields': ('ifood_customer_id', 'anotaai_customer_id'),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {'ativo': '#16a34a', 'inativo': '#9ca3af', 'bloqueado': '#dc2626'}
        color = colors.get(obj.status, '#9ca3af')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def integracoes(self, obj):
        badges = []
        if obj.tem_integracao_ifood:
            badges.append('<span style="background:#ea580c;color:white;padding:2px 6px;border-radius:4px;font-size:10px">iFood</span>')
        if obj.tem_integracao_anotaai:
            badges.append('<span style="background:#7c3aed;color:white;padding:2px 6px;border-radius:4px;font-size:10px">AnotaAI</span>')
        return format_html(' '.join(badges)) if badges else '-'
    integracoes.short_description = 'Integrações'


@admin.register(TagCliente)
class TagAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cor_preview', 'total_clientes']

    def cor_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:16px;height:16px;background:{};border-radius:3px;vertical-align:middle"></span> {}',
            obj.cor, obj.cor
        )
    cor_preview.short_description = 'Cor'

    def total_clientes(self, obj):
        return obj.clientes.count()
    total_clientes.short_description = 'Clientes'
