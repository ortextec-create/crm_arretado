from django.contrib import admin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'role', 'ativo', 'last_login', 'criado_em']
    list_filter   = ['role', 'ativo']
    search_fields = ['name', 'email']
    readonly_fields = ['criado_em', 'atualizado_em', 'last_login', 'password']
    ordering      = ['name']

    fieldsets = (
        ('Dados', {'fields': ('name', 'email', 'role', 'ativo')}),
        ('Permissões', {'fields': ('perms',)}),
        ('Controle', {'fields': ('password', 'last_login', 'criado_em', 'atualizado_em')}),
    )
