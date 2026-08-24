from rest_framework import serializers

from .models import Empresa


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = [
            'id', 'nome', 'subtitulo', 'razao_social', 'cnpj', 'padrao', 'ativo', 'criado_em',
            'cor_fundo', 'cor_surface', 'cor_surface_alt', 'cor_borda', 'cor_texto', 'cor_muted',
            'cor_primaria', 'cor_primaria_texto', 'cor_acento',
            'cor_sidebar', 'cor_sidebar_texto', 'cor_sidebar_ativo',
            'logo_horizontal', 'logo_negativo', 'logo_simbolo', 'timbre',
            'modulos_ocultos',
        ]
        read_only_fields = ['id', 'criado_em']

    def validate(self, attrs):
        padrao_final = attrs.get('padrao', self.instance.padrao if self.instance else False)

        if padrao_final:
            qs = Empresa.objects.filter(padrao=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'padrao': 'Já existe uma empresa padrão. Desmarque-a antes de definir outra.',
                })
        elif self.instance and self.instance.padrao:
            raise serializers.ValidationError({
                'padrao': 'Sempre precisa existir uma empresa padrão — marque outra como padrão antes de desmarcar esta.',
            })

        return attrs


class EmpresaBrandingSerializer(serializers.ModelSerializer):
    """Payload público (tela de login) — sem CNPJ/razão social, só o necessário pra montar a marca."""

    class Meta:
        model = Empresa
        fields = [
            'nome', 'subtitulo',
            'cor_fundo', 'cor_surface', 'cor_surface_alt', 'cor_borda', 'cor_texto', 'cor_muted',
            'cor_primaria', 'cor_primaria_texto', 'cor_acento',
            'cor_sidebar', 'cor_sidebar_texto', 'cor_sidebar_ativo',
            'logo_horizontal', 'logo_negativo', 'logo_simbolo',
        ]


class EmpresaResumoSerializer(serializers.ModelSerializer):
    """
    Resumo reusado fora do módulo Empresas (login, empresas vinculadas de um
    Usuario, resposta de definir-empresa-ativa/) — mesmos campos do branding
    (nome/cores/logos) + `id`, necessário pra selecionar/trocar de empresa.
    """

    class Meta:
        model = Empresa
        fields = [
            'id', 'nome', 'subtitulo',
            'cor_fundo', 'cor_surface', 'cor_surface_alt', 'cor_borda', 'cor_texto', 'cor_muted',
            'cor_primaria', 'cor_primaria_texto', 'cor_acento',
            'cor_sidebar', 'cor_sidebar_texto', 'cor_sidebar_ativo',
            'logo_horizontal', 'logo_negativo', 'logo_simbolo',
            'modulos_ocultos',
        ]
