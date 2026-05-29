from rest_framework import serializers
from .models import Usuario, PERMS_DEFAULT


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer completo — usado em list, retrieve, create e update."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_login = serializers.DateTimeField(read_only=True, format='%d/%m/%Y %H:%M', default=None)

    class Meta:
        model = Usuario
        fields = [
            'id', 'name', 'email', 'role', 'password',
            'perms', 'ativo', 'last_login', 'criado_em',
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
        return usuario

    def update(self, instance, validated_data):
        raw_password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if raw_password:
            instance.set_password(raw_password)
        instance.save()
        return instance


class RedefinirSenhaSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=6, write_only=True)
