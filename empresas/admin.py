from django.contrib import admin
from .models import Empresa


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'cnpj', 'padrao', 'ativo', 'criado_em')
    list_filter   = ('ativo', 'padrao')
    search_fields = ('nome', 'razao_social', 'cnpj')
    ordering      = ('-padrao', 'nome')
