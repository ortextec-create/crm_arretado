from django.contrib import admin

from .models import LogAuditoria


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['criado_em', 'acao', 'usuario_nome_snapshot', 'ip']
    list_filter = ['acao']
    search_fields = ['usuario_nome_snapshot']
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
