from rest_framework import serializers

from .models import LogAuditoria


class LogAuditoriaSerializer(serializers.ModelSerializer):
    acao_display = serializers.CharField(source='get_acao_display', read_only=True)

    class Meta:
        model = LogAuditoria
        fields = ['id', 'usuario', 'usuario_nome_snapshot', 'acao', 'acao_display', 'detalhes', 'ip', 'criado_em']
        read_only_fields = fields
