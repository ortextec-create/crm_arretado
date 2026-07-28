from django.contrib import admin

from .models import ConfiguracaoBackup, TelefoneAlertaBackup


@admin.register(ConfiguracaoBackup)
class ConfiguracaoBackupAdmin(admin.ModelAdmin):
    list_display = ['ativo', 'pasta_backup_db', 'pasta_backup_media', 'retencao_local_dias', 'retencao_remota_dias']


@admin.register(TelefoneAlertaBackup)
class TelefoneAlertaBackupAdmin(admin.ModelAdmin):
    list_display = ['nome', 'numero', 'ativo']
