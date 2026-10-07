from rest_framework import serializers

from eventos.models import Evento
from usuarios.models import Usuario

from .mensagens import validar_texto
from .models import (
    ConfiguracaoCobranca, EtapaRegua, PausaCobranca, LigacaoCobranca, EnvioCobranca,
)
from .regua import tipo_da_etapa


class ConfiguracaoCobrancaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoCobranca
        fields = [
            'id', 'ativo', 'ativo_desde', 'limite_lembrete', 'dias_semana_envio',
            'chave_pix', 'favorecido_pix', 'telefone_contato', 'intervalo_envio_segundos',
            'notificar_equipe_ultima_etapa',
            'msg_prazo_hoje_ativo', 'msg_prazo_hoje',
            'msg_prazo_vencido_ativo', 'msg_prazo_vencido',
            'msg_ligacao_nao_atendida_ativo', 'msg_ligacao_nao_atendida',
            'atualizado_em',
        ]
        read_only_fields = ['id', 'ativo_desde', 'atualizado_em']

    def validate_dias_semana_envio(self, value):
        if not value:
            raise serializers.ValidationError('Selecione ao menos um dia da semana.')
        if any(not isinstance(d, int) or d < 0 or d > 6 for d in value):
            raise serializers.ValidationError('Dias da semana devem ser inteiros de 0 (segunda) a 6 (domingo).')
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Dias da semana não podem repetir.')
        return sorted(value)

    def validate_msg_prazo_hoje(self, value):
        validar_texto(value, permitir_prazo=False)
        return value

    def validate_msg_prazo_vencido(self, value):
        validar_texto(value, permitir_prazo=True)
        return value

    def validate_msg_ligacao_nao_atendida(self, value):
        validar_texto(value, permitir_prazo=False)
        return value


class EtapaReguaSerializer(serializers.ModelSerializer):
    tipo = serializers.SerializerMethodField()
    rotulo = serializers.SerializerMethodField()

    class Meta:
        model = EtapaRegua
        fields = ['id', 'dias', 'mensagem', 'ativo', 'tipo', 'rotulo', 'criado_em', 'atualizado_em']
        read_only_fields = ['id', 'criado_em', 'atualizado_em']

    def get_tipo(self, obj):
        limite = self.context.get('limite')
        if limite is None:
            limite = ConfiguracaoCobranca.get().limite_lembrete
        return tipo_da_etapa(obj.dias, limite)

    def get_rotulo(self, obj):
        rotulos_map = self.context.get('rotulos_map')
        if rotulos_map is None:
            return ''
        return rotulos_map.get(obj.id, '')

    def validate_mensagem(self, value):
        if len(value or '') > 1000:
            raise serializers.ValidationError('A mensagem não pode passar de 1000 caracteres.')
        validar_texto(value, permitir_prazo=False)
        return value

    def validate_dias(self, value):
        qs = EtapaRegua.objects.filter(dias=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Já existe uma etapa em D{value:+d}.')
        return value


class EtapaPreviewSerializer(serializers.Serializer):
    mensagem = serializers.CharField()
    evento_id = serializers.IntegerField(required=False, allow_null=True)
    tipo_especial = serializers.ChoiceField(
        choices=['prazo_hoje', 'prazo_vencido', 'ligacao_nao_atendida'], required=False, allow_null=True,
    )


class EnvioCobrancaSerializer(serializers.ModelSerializer):
    evento_numero = serializers.CharField(source='evento.numero', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EnvioCobranca
        fields = [
            'id', 'evento', 'evento_numero', 'tipo', 'tipo_display', 'etapa', 'dias_etapa',
            'rotulo_etapa', 'data_evento_referencia', 'pausa', 'ligacao', 'status', 'status_display',
            'motivo_pulada', 'telefone', 'mensagem_renderizada', 'saldo_no_envio', 'criado_em',
        ]
        read_only_fields = fields


class PausaCobrancaSerializer(serializers.ModelSerializer):
    evento_numero = serializers.CharField(source='evento.numero', read_only=True)
    vigente = serializers.BooleanField(read_only=True)

    class Meta:
        model = PausaCobranca
        fields = [
            'id', 'evento', 'evento_numero', 'pausado_ate', 'motivo', 'origem', 'ligacao',
            'vigente', 'criado_por', 'criado_por_nome', 'criado_em',
            'encerrada_em', 'encerrada_por', 'encerrada_por_nome', 'motivo_encerramento',
        ]
        read_only_fields = [
            'id', 'origem', 'ligacao', 'vigente', 'criado_por', 'criado_por_nome', 'criado_em',
            'encerrada_em', 'encerrada_por', 'encerrada_por_nome', 'motivo_encerramento',
        ]

    def validate_pausado_ate(self, value):
        from django.utils import timezone
        if value < timezone.localdate():
            raise serializers.ValidationError('O prazo não pode estar no passado.')
        return value

    def validate_motivo(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o motivo da pausa.')
        return value


class EncerrarPausaSerializer(serializers.Serializer):
    motivo = serializers.CharField()

    def validate_motivo(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Informe o motivo da retomada.')
        return value


class LigacaoCobrancaSerializer(serializers.ModelSerializer):
    evento_numero = serializers.CharField(source='evento.numero', read_only=True)
    pausar = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = LigacaoCobranca
        fields = [
            'id', 'evento', 'evento_numero', 'data_hora', 'atendente', 'atendente_nome',
            'telefone_discado', 'atendeu', 'prazo_pagamento', 'observacao', 'pausar',
            'registrado_por', 'registrado_por_nome', 'criado_em',
        ]
        read_only_fields = [
            'id', 'atendente_nome', 'registrado_por', 'registrado_por_nome', 'criado_em',
        ]

    def validate_data_hora(self, value):
        from django.utils import timezone
        if value > timezone.now():
            raise serializers.ValidationError('A data/hora não pode estar no futuro.')
        return value

    def validate(self, attrs):
        if attrs.get('prazo_pagamento') and not attrs.get('atendeu'):
            raise serializers.ValidationError(
                {'prazo_pagamento': ['Só pode ser informado quando o cliente atendeu.']}
            )
        if attrs.get('prazo_pagamento'):
            from django.utils import timezone
            if attrs['prazo_pagamento'] < timezone.localdate():
                raise serializers.ValidationError({'prazo_pagamento': ['Não pode estar no passado.']})
        return attrs
