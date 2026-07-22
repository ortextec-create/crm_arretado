from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from auditoria.mixins import AuditoriaDestroyMixin, AuditoriaStatusMixin, AuditoriaUpdateMixin
from auditoria.models import LogAuditoria
from auditoria.utils import ator_ou_none, registrar
from usuarios.authentication import TokenAuthentication

from .models import (
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    Fornecedor,
    MovimentoFinanceiro,
    TelefoneAlertaFinanceiro,
)
from .serializers import (
    BaixaContaSerializer,
    CategoriaFinanceiraSerializer,
    ConfiguracaoFinanceiraSerializer,
    ContaBancariaSerializer,
    ContaPagarSerializer,
    FornecedorSerializer,
    MovimentoFinanceiroSerializer,
    TelefoneAlertaFinanceiroSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─── Categorias ────────────────────────────────────────────────────────────────

class CategoriaFinanceiraViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = CategoriaFinanceira.objects.select_related('pai').all()
    serializer_class = CategoriaFinanceiraSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome', 'tipo']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated()]
        return [AllowAny()]


# ─── Contas bancárias ──────────────────────────────────────────────────────────

class ContaBancariaViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = ContaBancaria.objects.all()
    serializer_class = ContaBancariaSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated()]
        return [AllowAny()]


# ─── Fornecedores ──────────────────────────────────────────────────────────────

class FornecedorViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = Fornecedor.objects.select_related('categoria_padrao').all()
    serializer_class = FornecedorSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['nome', 'cnpj']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(nome__icontains=search) | Q(cnpj__icontains=search))
        return qs


# ─── Configuração Financeira (singleton) ──────────────────────────────────────

class ConfiguracaoFinanceiraViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class = ConfiguracaoFinanceiraSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoFinanceira.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config = self.get_object()
        campos = list(request.data.keys())
        antes = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        serializer = ConfiguracaoFinanceiraSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_CONFIG_FINANCEIRA_ALTERADA,
            detalhes={'antes': antes, 'depois': depois},
            request=request,
        )
        return Response(serializer.data)


# ─── Telefones de Alerta Financeiro ────────────────────────────────────────────

class TelefoneAlertaFinanceiroViewSet(AuditoriaDestroyMixin, CsrfExemptMixin, viewsets.ModelViewSet):
    queryset = TelefoneAlertaFinanceiro.objects.all()
    serializer_class = TelefoneAlertaFinanceiroSerializer
    authentication_classes = [TokenAuthentication]
    campos_log_exclusao = ['numero', 'nome']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAuthenticated()]
        return [AllowAny()]


# ─── Ledger (só leitura) ───────────────────────────────────────────────────────

class MovimentoFinanceiroViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    queryset = (
        MovimentoFinanceiro.objects
        .select_related('conta', 'categoria', 'fornecedor', 'cliente', 'criado_por')
        .all()
    )
    serializer_class = MovimentoFinanceiroSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('conta'):
            qs = qs.filter(conta_id=params['conta'])
        if params.get('tipo'):
            qs = qs.filter(tipo=params['tipo'])
        if params.get('categoria'):
            qs = qs.filter(categoria_id=params['categoria'])
        if params.get('data_inicio'):
            qs = qs.filter(data_movimento__gte=params['data_inicio'])
        if params.get('data_fim'):
            qs = qs.filter(data_movimento__lte=params['data_fim'])
        return qs


# ─── Contas a Pagar ────────────────────────────────────────────────────────────

class ContaPagarViewSet(
    AuditoriaStatusMixin, AuditoriaUpdateMixin,
    CsrfExemptMixin, viewsets.ModelViewSet,
):
    queryset = ContaPagar.objects.select_related('fornecedor', 'categoria').all()
    serializer_class = ContaPagarSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    campos_log_criacao = ['numero', 'descricao', 'valor', 'data_vencimento']
    campos_log_atualizacao = [
        'fornecedor', 'descricao', 'categoria', 'valor', 'data_emissao',
        'data_vencimento', 'observacao',
    ]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'baixa', 'cancelar'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        if params.get('categoria'):
            qs = qs.filter(categoria_id=params['categoria'])
        if params.get('fornecedor'):
            qs = qs.filter(fornecedor_id=params['fornecedor'])
        mes = params.get('mes')
        if mes:
            try:
                ano_s, mes_s = mes.split('-')
                qs = qs.filter(data_vencimento__year=int(ano_s), data_vencimento__month=int(mes_s))
            except (ValueError, AttributeError):
                pass
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(numero__icontains=search) | Q(descricao__icontains=search) | Q(fornecedor__nome__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(numero=ContaPagar.proximo_numero())
        instance = serializer.instance
        detalhes = {
            'model': instance.__class__.__name__, 'id': instance.pk, 'descricao': str(instance),
        }
        for campo in self.campos_log_criacao:
            detalhes[campo] = str(getattr(instance, campo, None))
        registrar(ator_ou_none(self.request), LogAuditoria.ACAO_REGISTRO_CRIADO, detalhes=detalhes, request=self.request)

    def update(self, request, *args, **kwargs):
        conta = self.get_object()
        if conta.status != 'pendente':
            return Response(
                {'detail': 'Só é possível editar contas com status Pendente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(conta, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='baixa')
    def baixa(self, request, pk=None):
        conta_pagar = self.get_object()
        if conta_pagar.status in ('paga', 'cancelada'):
            return Response(
                {'detail': f'Conta já está {conta_pagar.get_status_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BaixaContaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        saldo_restante = conta_pagar.valor - conta_pagar.valor_pago
        if dados['valor'] > saldo_restante:
            raise ValidationError({'valor': f'Maior que o saldo restante (R$ {saldo_restante}).'})

        try:
            mov = MovimentoFinanceiro.registrar(
                conta=dados['conta'], tipo='saida', valor=dados['valor'],
                data_movimento=dados['data'], categoria=conta_pagar.categoria,
                fornecedor=conta_pagar.fornecedor,
                descricao=f'Baixa {conta_pagar.numero} — {conta_pagar.descricao}'.strip(' —'),
                forma_pagamento=dados['forma'], origem_tipo='conta_pagar', origem_id=conta_pagar.id,
                comprovante=dados.get('comprovante'), criado_por=request.user,
            )
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

        conta_pagar.refresh_from_db()
        conta_pagar.recalcular_valor_pago()

        registrar(
            request.user, LogAuditoria.ACAO_BAIXA_REGISTRADA,
            detalhes={
                'model': 'ContaPagar', 'id': conta_pagar.id, 'numero': conta_pagar.numero,
                'valor_baixado': str(dados['valor']), 'movimento_id': mov.id,
            },
            request=request,
        )
        return Response(ContaPagarSerializer(conta_pagar).data)

    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        conta_pagar = self.get_object()
        if conta_pagar.valor_pago > 0:
            return Response(
                {'detail': 'Não é possível cancelar uma conta com valor já pago — estorne a baixa manualmente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        de = conta_pagar.status
        conta_pagar.status = 'cancelada'
        conta_pagar.save(update_fields=['status', 'atualizado_em'])
        self.log_mudanca_status(conta_pagar, de=de, para='cancelada')
        return Response(ContaPagarSerializer(conta_pagar).data)

    @action(detail=False, methods=['get'], url_path='resumo')
    def resumo(self, request):
        hoje = timezone.localdate()
        abertas = ContaPagar.objects.filter(status__in=['pendente', 'parcial'])

        em_atraso = abertas.filter(data_vencimento__lt=hoje).count()
        vence_hoje = abertas.filter(data_vencimento=hoje).count()
        proximos_7_dias = abertas.filter(
            data_vencimento__gt=hoje, data_vencimento__lte=hoje + timedelta(days=7),
        ).count()

        inicio_mes = hoje.replace(day=1)
        pago_mes = MovimentoFinanceiro.objects.filter(
            origem_tipo='conta_pagar', tipo='saida',
            data_movimento__gte=inicio_mes, data_movimento__lte=hoje,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')
        pendente_mes = abertas.filter(
            data_vencimento__year=hoje.year, data_vencimento__month=hoje.month,
        ).aggregate(t=Sum(F('valor') - F('valor_pago')))['t'] or Decimal('0')

        return Response({
            'em_atraso': em_atraso,
            'vence_hoje': vence_hoje,
            'proximos_7_dias': proximos_7_dias,
            'total_mes': {'pago': pago_mes, 'pendente': pendente_mes},
        })
