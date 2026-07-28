from rest_framework import serializers

from .models import ConfiguracaoBackup, TelefoneAlertaBackup


class ConfiguracaoBackupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoBackup
        fields = [
            'ativo', 'pasta_backup_db', 'pasta_backup_media',
            'retencao_local_dias', 'retencao_remota_dias',
            'rclone_remote', 'rclone_pasta_remota', 'envio_externo_ativo',
            'horas_limite_alerta', 'tamanho_minimo_kb', 'atualizado_em',
        ]
        read_only_fields = ['atualizado_em']


class TelefoneAlertaBackupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelefoneAlertaBackup
        fields = ['id', 'numero', 'nome', 'ativo', 'criado_em']
