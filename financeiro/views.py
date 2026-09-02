from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from auditoria.mixins import AuditoriaDestroyMixin, AuditoriaStatusMixin, AuditoriaUpdateMixin
from auditoria.models import LogAuditoria
from auditoria.utils import ator_ou_none, registrar
from empresas.models import Empresa
from usuarios.authentication import TokenAuthentication

from .models import (
    CategoriaFinanceira,
    ConfiguracaoFinanceira,
    ContaBancaria,
    ContaPagar,
    ContaReceber,
    DespesaRecorrente,
    Fornecedor,
    MovimentoFinanceiro,
    SaldoConferido,
    TelefoneAlertaFinanceiro,
)
from .serializers import (
    BaixaContaSerializer,
    CategoriaFinanceiraSerializer,
    ConfiguracaoFinanceiraSerializer,
    ContaBancariaSerializer,
    ContaPagarSerializer,
    ContaReceberSerializer,
    DespesaRecorrenteSerializer,
    FornecedorSerializer,
    MovimentoFinanceiroSerializer,
    MovimentoManualSerializer,
    SaldoConferidoSerializer,
    TelefoneAlertaFinanceiroSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


def _resolver_empresa(request):
    """
    Resolve a empresa do request (Fase 4 do multi-empresa): `?empresa=<id>`
    explícito > `empresa_ativa` do usuário autenticado > `Empresa.get_padrao()`
    — nunca `.objects.first()`. `?empresa=todas` devolve None, sentinela de
    "consolidado" (usado nos agregadores/resumos).
    """
    param = request.query_params.get('empresa')
    if param == 'todas':
        return None
    if param:
        return get_object_or_404(Empresa, pk=param)
    user = request.user
    if getattr(user, 'is_authenticated', False) and getattr(user, 'empresa_ativa_id', None):
        return user.empresa_ativa
    return Empresa.get_padrao()


def _empresas_do_usuario(usuario):
    """Mesma regra de usuarios.views._empresas_efetivas — admin vê todas as ativas, demais só as vinculadas."""
    if usuario.role == 'admin':
        return list(Empresa.objects.filter(ativo=True))
    vinculadas = list(usuario.empresas.filter(ativo=True))
    return vinculadas or [Empresa.get_padrao()]


def _validar_empresa_vinculo(request, empresa):
    """Actions IsAuthenticated: rejeita ?empresa=<id> fora do vínculo do usuário (exceto admin)."""
    if empresa not in _empresas_do_usuario(request.user):
        raise ValidationError({'empresa': 'Empresa fora do vínculo do usuário.'})


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
    queryset = ContaBancaria.objects.select_related('empresa').all()
    serializer_class = ContaBancariaSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        empresa = _resolver_empresa(self.request)
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        return qs

    def perform_create(self, serializer):
        empresa = _resolver_empresa(self.request)
        _validar_empresa_vinculo(self.request, empresa)
        serializer.save(empresa=empresa)


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
        empresa = _resolver_empresa(self.request) or Empresa.get_padrao()
        return ConfiguracaoFinanceira.get(empresa)

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
    """
    Ledger — só leitura, exceto a action `manual/` (lançamento avulso ou
    estorno). Nunca implementar DELETE nem criar movimento fora de
    MovimentoFinanceiro.registrar() — ver "O Que NÃO Fazer" no CLAUDE.md.
    """
    queryset = (
        MovimentoFinanceiro.objects
        .select_related('conta', 'conta__empresa', 'categoria', 'fornecedor', 'cliente', 'criado_por')
        .all()
    )
    serializer_class = MovimentoFinanceiroSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'manual':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        empresa = _resolver_empresa(self.request)
        if empresa is not None:
            qs = qs.filter(conta__empresa=empresa)
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

    @action(detail=False, methods=['post'], url_path='manual')
    def manual(self, request):
        serializer = MovimentoManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        _validar_empresa_vinculo(request, dados['conta'].empresa)

        try:
            mov = MovimentoFinanceiro.registrar(
                conta=dados['conta'], tipo=dados['tipo'], valor=dados['valor'],
                data_movimento=dados.get('data_movimento'),
                categoria=dados.get('categoria'), fornecedor=dados.get('fornecedor'),
                cliente=dados.get('cliente'), descricao=dados.get('descricao', ''),
                forma_pagamento=dados.get('forma_pagamento', ''), origem_tipo='manual',
                comprovante=dados.get('comprovante'), criado_por=request.user,
            )
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

        registrar(
            request.user, LogAuditoria.ACAO_MOVIMENTO_MANUAL,
            detalhes={
                'movimento_id': mov.id, 'tipo': mov.tipo, 'valor': str(mov.valor),
                'conta': mov.conta.nome, 'descricao': mov.descricao,
            },
            request=request,
        )
        return Response(MovimentoFinanceiroSerializer(mov).data, status=status.HTTP_201_CREATED)


# ─── Contas a Pagar ────────────────────────────────────────────────────────────

class ContaPagarViewSet(
    AuditoriaStatusMixin, AuditoriaUpdateMixin,
    CsrfExemptMixin, viewsets.ModelViewSet,
):
    queryset = ContaPagar.objects.select_related('empresa', 'fornecedor', 'categoria').all()
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

        empresa = _resolver_empresa(self.request)
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # Filtro por "bucket" de vencimento — usado pelos KPIs clicáveis da tela
        # (Em atraso / Vence hoje / Próx. 7 dias). Cada um implica conta aberta.
        vencimento = params.get('vencimento')
        if vencimento in ('atraso', 'hoje', 'proximos_7'):
            hoje = timezone.localdate()
            qs = qs.filter(status__in=['pendente', 'parcial'])
            if vencimento == 'atraso':
                qs = qs.filter(data_vencimento__lt=hoje)
            elif vencimento == 'hoje':
                qs = qs.filter(data_vencimento=hoje)
            else:  # proximos_7
                qs = qs.filter(data_vencimento__gt=hoje, data_vencimento__lte=hoje + timedelta(days=7))

        # KPI "Pago no mês": contas que receberam ao menos uma baixa no mês corrente
        # (mesma fonte do card — MovimentoFinanceiro origem_tipo='conta_pagar').
        if params.get('pago_mes') in ('1', 'true'):
            hoje = timezone.localdate()
            inicio_mes = hoje.replace(day=1)
            baixadas = (
                MovimentoFinanceiro.objects
                .filter(origem_tipo='conta_pagar', tipo='saida',
                        data_movimento__gte=inicio_mes, data_movimento__lte=hoje)
                .values_list('origem_id', flat=True)
            )
            ids = [int(x) for x in baixadas if str(x).isdigit()]
            qs = qs.filter(id__in=ids)

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
        empresa = _resolver_empresa(self.request)
        _validar_empresa_vinculo(self.request, empresa)
        serializer.save(numero=ContaPagar.proximo_numero(), empresa=empresa)
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
        empresa = _resolver_empresa(request)
        abertas = ContaPagar.objects.filter(status__in=['pendente', 'parcial'])
        movimentos = MovimentoFinanceiro.objects.all()
        if empresa is not None:
            abertas = abertas.filter(empresa=empresa)
            movimentos = movimentos.filter(conta__empresa=empresa)

        em_atraso = abertas.filter(data_vencimento__lt=hoje).count()
        vence_hoje = abertas.filter(data_vencimento=hoje).count()
        proximos_7_dias = abertas.filter(
            data_vencimento__gt=hoje, data_vencimento__lte=hoje + timedelta(days=7),
        ).count()

        inicio_mes = hoje.replace(day=1)
        pago_mes = movimentos.filter(
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


# ─── Contas a Receber ──────────────────────────────────────────────────────────

class ContaReceberViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    """
    POST cria só lançamento manual (canal/origem_canal forçados em
    perform_create) — os automáticos (iFood repasse) vêm do signal em
    financeiro/signals.py. Eventos nunca aparecem aqui: o saldo deles é
    consultado dinamicamente em resumo/, nunca materializado como linha.
    """
    queryset = ContaReceber.objects.select_related('empresa', 'cliente', 'categoria').all()
    serializer_class = ContaReceberSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'baixa'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        empresa = _resolver_empresa(self.request)
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        if params.get('canal'):
            qs = qs.filter(canal=params['canal'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        mes = params.get('mes')
        if mes:
            try:
                ano_s, mes_s = mes.split('-')
                qs = qs.filter(data_vencimento__year=int(ano_s), data_vencimento__month=int(mes_s))
            except (ValueError, AttributeError):
                pass
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(numero__icontains=search) | Q(cliente_nome__icontains=search) | Q(referencia__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        empresa = _resolver_empresa(self.request)
        _validar_empresa_vinculo(self.request, empresa)
        serializer.save(numero=ContaReceber.proximo_numero(), canal='manual', origem_canal='manual', empresa=empresa)

    @action(detail=True, methods=['post'], url_path='baixa')
    def baixa(self, request, pk=None):
        conta_receber = self.get_object()
        if conta_receber.status in ('recebida', 'cancelada'):
            return Response(
                {'detail': f'Conta já está {conta_receber.get_status_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BaixaContaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        saldo_restante = conta_receber.valor - conta_receber.valor_recebido
        if dados['valor'] > saldo_restante:
            raise ValidationError({'valor': f'Maior que o saldo restante (R$ {saldo_restante}).'})

        try:
            mov = MovimentoFinanceiro.registrar(
                conta=dados['conta'], tipo='entrada', valor=dados['valor'],
                data_movimento=dados['data'], categoria=conta_receber.categoria,
                cliente=conta_receber.cliente,
                descricao=f'Recebimento {conta_receber.numero}',
                forma_pagamento=dados['forma'], origem_tipo='conta_receber', origem_id=conta_receber.id,
                comprovante=dados.get('comprovante'), criado_por=request.user,
            )
        except DjangoValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

        conta_receber.refresh_from_db()
        conta_receber.recalcular_valor_recebido()

        registrar(
            request.user, LogAuditoria.ACAO_BAIXA_REGISTRADA,
            detalhes={
                'model': 'ContaReceber', 'id': conta_receber.id, 'numero': conta_receber.numero,
                'valor_recebido': str(dados['valor']), 'movimento_id': mov.id,
            },
            request=request,
        )
        return Response(ContaReceberSerializer(conta_receber).data)

    @action(detail=False, methods=['get'], url_path='resumo')
    def resumo(self, request):
        from eventos.models import Evento

        hoje = timezone.localdate()
        limite30 = hoje + timedelta(days=30)
        empresa = _resolver_empresa(request)

        movimentos = MovimentoFinanceiro.objects.all()
        abertas = ContaReceber.objects.filter(status__in=['pendente', 'parcial'])
        if empresa is not None:
            movimentos = movimentos.filter(conta__empresa=empresa)
            abertas = abertas.filter(empresa=empresa)

        recebido_hoje = movimentos.filter(
            tipo='entrada', data_movimento=hoje,
        ).aggregate(t=Sum('valor'))['t'] or Decimal('0')

        a_receber_contas = abertas.aggregate(t=Sum(F('valor') - F('valor_recebido')))['t'] or Decimal('0')
        proximos_contas = abertas.filter(
            data_vencimento__gte=hoje, data_vencimento__lte=limite30,
        ).aggregate(t=Sum(F('valor') - F('valor_recebido')))['t'] or Decimal('0')

        # Eventos pertence só à matriz (mono-empresa por escopo) — só entra no
        # consolidado ("todas") ou quando a empresa filtrada é a própria matriz.
        a_receber_eventos = proximos_eventos = Decimal('0')
        if empresa is None or empresa == Empresa.get_padrao():
            eventos_abertos = (
                Evento.objects.exclude(status__in=['cancelado', 'entregue'])
                .annotate(saldo=F('valor_total') - F('sinal_pago'))
                .filter(saldo__gt=0)
            )
            a_receber_eventos = eventos_abertos.aggregate(t=Sum('saldo'))['t'] or Decimal('0')
            proximos_eventos = eventos_abertos.filter(
                data_evento__gte=hoje, data_evento__lte=limite30,
            ).aggregate(t=Sum('saldo'))['t'] or Decimal('0')

        return Response({
            'recebido_hoje': recebido_hoje,
            'a_receber': a_receber_contas + a_receber_eventos,
            'proximos_30_dias': proximos_contas + proximos_eventos,
        })


# ─── Despesas Recorrentes ──────────────────────────────────────────────────────

class DespesaRecorrenteViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    """
    Molde de despesa mensal — sem DELETE (pausar via PATCH ativo=False,
    nunca deletar; PROTECT em ContaPagar.recorrente cobre isso de qualquer forma).
    """
    queryset = DespesaRecorrente.objects.select_related('empresa', 'fornecedor', 'categoria').all()
    serializer_class = DespesaRecorrenteSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        empresa = _resolver_empresa(self.request)
        if empresa is not None:
            qs = qs.filter(empresa=empresa)
        return qs

    def perform_create(self, serializer):
        empresa = _resolver_empresa(self.request)
        _validar_empresa_vinculo(self.request, empresa)
        serializer.save(empresa=empresa)


# ─── Conferência de Saldo ──────────────────────────────────────────────────────

class SaldoConferidoViewSet(CsrfExemptMixin, viewsets.ModelViewSet):
    """
    Só GET/POST — sem edição (nova conferência substitui a leitura anterior
    na UI, histórico preservado no banco). saldo_calculado nunca vem do
    payload: é sempre o snapshot de ContaBancaria.saldo_atual no momento
    do POST.
    """
    queryset = SaldoConferido.objects.select_related('conta', 'criado_por').all()
    serializer_class = SaldoConferidoSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('conta'):
            qs = qs.filter(conta_id=self.request.query_params['conta'])
        return qs

    def perform_create(self, serializer):
        conta = serializer.validated_data['conta']
        serializer.save(saldo_calculado=conta.saldo_atual, criado_por=self.request.user)


# ─── Fluxo de Caixa (agregador, sem model próprio) ─────────────────────────────

class FluxoCaixaView(CsrfExemptMixin, views.APIView):
    """
    GET /financeiro/fluxo-caixa/?dias=14 — janela de `dias` a partir de hoje
    (hoje incluso). Por dia: entrada/saida realizada (soma do ledger nessa
    data_movimento) e projetada (soma do saldo restante de ContaPagar/
    ContaReceber pendente/parcial com esse data_vencimento — já inclui
    contas geradas por DespesaRecorrente, é a mesma query genérica).
    Não inclui o saldo dinâmico de Evento (diferente de
    contas-receber/resumo) — fora do escopo literal da Fase 6.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            dias = int(request.query_params.get('dias', 14))
        except (TypeError, ValueError):
            dias = 14
        dias = max(1, min(dias, 90))

        hoje = timezone.localdate()
        fim = hoje + timedelta(days=dias - 1)
        empresa = _resolver_empresa(request)

        realizado_qs = MovimentoFinanceiro.objects.filter(data_movimento__gte=hoje, data_movimento__lte=fim)
        pagar_qs = ContaPagar.objects.filter(status__in=['pendente', 'parcial'], data_vencimento__gte=hoje, data_vencimento__lte=fim)
        receber_qs = ContaReceber.objects.filter(status__in=['pendente', 'parcial'], data_vencimento__gte=hoje, data_vencimento__lte=fim)
        if empresa is not None:
            realizado_qs = realizado_qs.filter(conta__empresa=empresa)
            pagar_qs = pagar_qs.filter(empresa=empresa)
            receber_qs = receber_qs.filter(empresa=empresa)

        realizado = realizado_qs.values('data_movimento', 'tipo').annotate(total=Sum('valor'))
        realizado_por_dia = {}
        for row in realizado:
            chave = row['data_movimento']
            realizado_por_dia.setdefault(chave, {'entrada': Decimal('0'), 'saida': Decimal('0')})
            realizado_por_dia[chave][row['tipo']] = row['total']

        pagar_projetado = pagar_qs.values('data_vencimento').annotate(total=Sum(F('valor') - F('valor_pago')))
        pagar_por_dia = {row['data_vencimento']: row['total'] for row in pagar_projetado}

        receber_projetado = receber_qs.values('data_vencimento').annotate(total=Sum(F('valor') - F('valor_recebido')))
        receber_por_dia = {row['data_vencimento']: row['total'] for row in receber_projetado}

        dias_resposta = []
        for i in range(dias):
            data = hoje + timedelta(days=i)
            r = realizado_por_dia.get(data, {})
            dias_resposta.append({
                'data': data,
                'entrada_realizada': r.get('entrada', Decimal('0')),
                'saida_realizada': r.get('saida', Decimal('0')),
                'entrada_projetada': receber_por_dia.get(data, Decimal('0')),
                'saida_projetada': pagar_por_dia.get(data, Decimal('0')),
            })

        contas_qs = ContaBancaria.objects.filter(ativo=True)
        if empresa is not None:
            contas_qs = contas_qs.filter(empresa=empresa)

        contas = []
        for conta in contas_qs:
            ultima = conta.conferencias.first()
            contas.append({
                'id': conta.id,
                'nome': conta.nome,
                'saldo_atual': conta.saldo_atual,
                'ultima_conferencia': {
                    'data': ultima.data,
                    'saldo_informado': ultima.saldo_informado,
                    'saldo_calculado': ultima.saldo_calculado,
                    'diferenca': ultima.diferenca,
                } if ultima else None,
            })

        return Response({'dias': dias_resposta, 'contas': contas})
