from rest_framework import serializers

from empresas.models import Empresa
from empresas.serializers import EmpresaResumoSerializer

from .models import Usuario, PERMS_DEFAULT


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer completo — usado em list, retrieve, create e update."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_login = serializers.DateTimeField(read_only=True, format='%d/%m/%Y %H:%M', default=None)

    # Multi-Empresa — Fase 2. Leitura nested (`empresas`/`empresa_ativa`) +
    # escrita por id (`empresas_ids`, mapeado via source pro campo M2M real).
    # `empresa_ativa` e `preferencia_tema` são sempre read-only aqui — só se
    # alteram via definir-empresa-ativa/ e preferencia-tema/ (ver views.py),
    # nunca por PATCH direto de outro usuário/admin.
    empresas = EmpresaResumoSerializer(many=True, read_only=True)
    empresas_ids = serializers.PrimaryKeyRelatedField(
        source='empresas', many=True, queryset=Empresa.objects.filter(ativo=True),
        write_only=True, required=False,
    )
    empresa_ativa = EmpresaResumoSerializer(read_only=True)
    preferencia_tema = serializers.CharField(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id', 'name', 'email', 'role', 'password',
            'perms', 'ativo', 'last_login', 'criado_em',
            'empresas', 'empresas_ids', 'empresa_ativa', 'preferencia_tema',
        ]
        read_only_fields = ['id', 'criado_em', 'last_login']

    def validate_email(self, value):
        qs = Usuario.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Já existe um usuário com este e-mail.')
        return value.lower()

    def create(self, validated_data):
        raw_password = validated_data.pop('password', None)
        empresas = validated_data.pop('empresas', None)
        role = validated_data.get('role', 'atendente')

        # Preenche perms com o padrão do perfil se não foi enviado
        if 'perms' not in validated_data or not validated_data['perms']:
            validated_data['perms'] = dict(PERMS_DEFAULT.get(role, {}))

        usuario = Usuario(**validated_data)
        if raw_password:
            usuario.set_password(raw_password)
        else:
            raise serializers.ValidationError({'password': 'A senha é obrigatória ao criar um usuário.'})
        usuario.save()
        if empresas is not None:
            usuario.empresas.set(empresas)
        return usuario

    def update(self, instance, validated_data):
        raw_password = validated_data.pop('password', None)
        empresas = validated_data.pop('empresas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if raw_password:
            instance.set_password(raw_password)
        instance.save()
        if empresas is not None:
            instance.empresas.set(empresas)
        return instance


class RedefinirSenhaSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=6, write_only=True)
