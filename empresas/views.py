from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from auditoria.mixins import AuditoriaCreateMixin, AuditoriaUpdateMixin
from usuarios.authentication import TokenAuthentication

from .models import Empresa
from .serializers import EmpresaBrandingSerializer, EmpresaSerializer


class CsrfExemptMixin:
    authentication_classes = []


class EmpresaViewSet(AuditoriaCreateMixin, AuditoriaUpdateMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    # Sobrescreve o [] do CsrfExemptMixin — create/update exigem login (ver get_permissions),
    # list/retrieve/branding-login continuam AllowAny.
    authentication_classes = [TokenAuthentication]
    # Sem DELETE/PUT — inativar é sempre ativo=False (mesma filosofia de DespesaRecorrente/ConfiguracaoIFood)
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    campos_log_criacao = ['nome', 'cnpj', 'padrao']
    campos_log_atualizacao = [
        'nome', 'subtitulo', 'razao_social', 'cnpj', 'padrao', 'ativo',
        'cor_fundo', 'cor_surface', 'cor_surface_alt', 'cor_borda', 'cor_texto', 'cor_muted',
        'cor_primaria', 'cor_primaria_texto', 'cor_acento',
        'cor_sidebar', 'cor_sidebar_texto', 'cor_sidebar_ativo',
    ]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated()]
        return [AllowAny()]

    @action(detail=False, methods=['get'], url_path='branding-login', authentication_classes=[], permission_classes=[AllowAny])
    def branding_login(self, request):
        empresa = Empresa.objects.filter(padrao=True).first()
        if not empresa:
            return Response({})
        return Response(EmpresaBrandingSerializer(empresa, context={'request': request}).data)
