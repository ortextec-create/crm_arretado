from datetime import datetime, time as dtime, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from eventos.models import Evento, TelefoneAlertaEvento
from notificacoes.servico import notificar
from usuarios.authentication import TokenAuthentication
from auditoria.models import LogAuditoria
from auditoria.utils import registrar, ator_ou_none

from .models import (
    ConfiguracaoCobranca, EtapaRegua, PausaCobranca, LigacaoCobranca, EnvioCobranca,
)
from .mensagens import render, montar_contexto, contexto_ficticio, variaveis_invalidas
from .regua import (
    eventos_elegiveis, tipo_da_etapa, rotulos, data_da_etapa, pausa_vigente,
)
from .serializers import (
    ConfiguracaoCobrancaSerializer, EtapaReguaSerializer, EtapaPreviewSerializer,
    EnvioCobrancaSerializer, PausaCobrancaSerializer, EncerrarPausaSerializer,
    LigacaoCobrancaSerializer,
)


class CsrfExemptMixin:
    authentication_classes = []


# ─────────────────────────────────────────────────────────────────────────────
# Configuração (singleton)
# ─────────────────────────────────────────────────────────────────────────────

class ConfiguracaoCobrancaViewSet(CsrfExemptMixin, viewsets.GenericViewSet):
    serializer_class = ConfiguracaoCobrancaSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'partial_update':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_object(self):
        return ConfiguracaoCobranca.get()

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def partial_update(self, request, pk=None):
        config = self.get_object()
        campos = list(request.data.keys())
        antes = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        ativo_antes = config.ativo

        serializer = ConfiguracaoCobrancaSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if 'ativo' in campos and ativo_antes is False and config.ativo is True:
            config.ativo_desde = timezone.localdate()
            config.save(update_fields=['ativo_desde'])

        depois = {c: str(getattr(config, c)) for c in campos if hasattr(config, c)}
        registrar(
            request.user, LogAuditoria.ACAO_COBRANCA_CONFIG_ALTERADA,
            detalhes={'antes': antes, 'depois': depois}, request=request,
        )
        return Response(ConfiguracaoCobrancaSerializer(config).data)


# ─────────────────────────────────────────────────────────────────────────────
# Etapas da régua
# ─────────────────────────────────────────────────────────────────────────────

class EtapaReguaViewSet(
    CsrfExemptMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = EtapaRegua.objects.all()
    serializer_class = EtapaReguaSerializer
    authentication_classes = [TokenAuthentication]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'partial_update'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        cfg = ConfiguracaoCobranca.get()
        etapas_ativas = list(EtapaRegua.objects.filter(ativo=True))
        ctx['limite'] = cfg.limite_lembrete
        ctx['rotulos_map'] = rotulos(etapas_ativas, cfg.limite_lembrete)
        return ctx

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        limite = ConfiguracaoCobranca.get().limite_lembrete
        if isinstance(response.data, dict):
            response.data['limite_lembrete'] = limite
        else:
            response.data = {'results': response.data, 'limite_lembrete': limite}
        return response

    def perform_create(self, serializer):
        serializer.save()
        instance = serializer.instance
        registrar(
            ator_ou_none(self.request), LogAuditoria.ACAO_COBRANCA_ETAPA_CRIADA,
            detalhes={'id': instance.id, 'dias': instance.dias}, request=self.request,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        campos = ['dias', 'mensagem', 'ativo']
        antes = {c: str(getattr(instance, c)) for c in campos}
        serializer.save()
        instance.refresh_from_db()
        depois = {c: str(getattr(instance, c)) for c in campos}
        mudou = {c: {'de': antes[c], 'para': depois[c]} for c in campos if antes[c] != depois[c]}
        if mudou:
            registrar(
                ator_ou_none(self.request), LogAuditoria.ACAO_COBRANCA_ETAPA_ALTERADA,
                detalhes={'id': instance.id, 'campos': mudou}, request=self.request,
            )

    @action(detail=False, methods=['post'])
    def preview(self, request):
        serializer = EtapaPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        mensagem = dados['mensagem']
        tipo_especial = dados.get('tipo_especial')
        permitir_prazo = tipo_especial in ('prazo_hoje', 'prazo_vencido')

        cfg = ConfiguracaoCobranca.get()
        hoje = timezone.localdate()

        evento = None
        evento_id = dados.get('evento_id')
        if evento_id:
            evento = Evento.objects.filter(pk=evento_id).first()
        if evento is None:
            evento = eventos_elegiveis().order_by('data_evento').first()

        contexto_e_ficticio = evento is None
        if evento is not None:
            pausa = None
            if permitir_prazo:
                pausa = pausa_vigente(evento, hoje)
                if pausa is None:
                    from types import SimpleNamespace
                    pausa = SimpleNamespace(pausado_ate=hoje + timedelta(days=5))
            ctx = montar_contexto(evento, cfg, hoje, pausa=pausa)
        else:
            ctx = contexto_ficticio(cfg, hoje, permitir_prazo=permitir_prazo)

        texto = render(mensagem, ctx)
        invalidas = variaveis_invalidas(mensagem, permitir_prazo=permitir_prazo)

        return Response({
            'texto': texto,
            'variaveis_invalidas': invalidas,
            'contexto_ficticio': contexto_e_ficticio,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Fila + linha do tempo (helpers de apresentação — reusam regua.py pra
# fase/próxima ação, nunca reimplementam a decisão)
# ─────────────────────────────────────────────────────────────────────────────

_RANK_FASE = {'concluida': 1, 'cobranca': 2, 'pausado': 3, 'lembrete': 4, 'aguardando': 5}


def _envios_atuais(evento):
    return [e for e in evento.envios_cobranca.all() if e.data_evento_referencia == evento.data_evento]


def _etapas_payload(evento, etapas_ativas, rotulos_map, hoje):
    envios = _envios_atuais(evento)
    enviados_ids = {e.etapa_id for e in envios if e.status == 'enviado' and e.etapa_id}
    puladas_ids = {e.etapa_id for e in envios if e.status == 'pulada' and e.etapa_id}

    payload = []
    for e in etapas_ativas:
        if e.id in enviados_ids:
            situacao = 'enviada'
        elif e.id in puladas_ids:
            situacao = 'pulada'
        elif data_da_etapa(evento, e) <= hoje:
            situacao = 'pendente'
        else:
            situacao = 'futura'
        payload.append({
            'id': e.id, 'rotulo': rotulos_map.get(e.id, ''), 'dias': e.dias,
            'data': data_da_etapa(evento, e).isoformat(), 'situacao': situacao,
        })
    return payload


def _fase_evento(evento, cfg, etapas_ativas, maior_dias_ativa, pausa, hoje):
    if pausa:
        return {'codigo': 'pausado', 'texto': f'Pausado até {pausa.pausado_ate.strftime("%d/%m")}'}

    envios = _envios_atuais(evento)
    enviados = sorted(
        (e for e in envios if e.status == 'enviado' and e.etapa_id), key=lambda e: e.dias_etapa,
    )
    if not enviados:
        return {'codigo': 'aguardando', 'texto': 'Ainda não começou'}

    ultima = enviados[-1]
    if ultima.dias_etapa == maior_dias_ativa:
        return {'codigo': 'concluida', 'texto': 'Régua concluída'}

    tipo = ultima.tipo if ultima.tipo in ('lembrete', 'cobranca') else tipo_da_etapa(ultima.dias_etapa, cfg.limite_lembrete)
    do_tipo = [e for e in etapas_ativas if tipo_da_etapa(e.dias, cfg.limite_lembrete) == tipo]
    pos = sum(1 for e in do_tipo if e.dias <= ultima.dias_etapa)
    texto_tipo = 'Lembrete' if tipo == 'lembrete' else 'Cobrança'
    return {'codigo': tipo, 'texto': f'{texto_tipo} {pos} de {len(do_tipo)}'}


def _proxima_acao(evento, etapas_ativas, rotulos_map, pausa, hoje, dias_para_evento):
    if pausa:
        if pausa.pausado_ate == hoje:
            return {'texto': 'Prazo combinado vence hoje', 'urgente': True}
        return {
            'texto': f'Retoma em {(pausa.pausado_ate + timedelta(days=1)).strftime("%d/%m")} se não pagar',
            'urgente': False,
        }
    prox = next(
        (e for e in sorted(etapas_ativas, key=lambda e: e.dias) if data_da_etapa(evento, e) > hoje), None,
    )
    if prox:
        return {
            'texto': f'{rotulos_map.get(prox.id, "")} em {data_da_etapa(evento, prox).strftime("%d/%m")}',
            'urgente': False,
        }
    return {'texto': 'Sem mensagens pendentes. Ligar.', 'urgente': dias_para_evento <= 0}


def _ultimo_contato(evento):
    candidatos = []
    for e in _envios_atuais(evento):
        if e.status == 'enviado':
            candidatos.append(('whatsapp', e.criado_em, None))
    for l in evento.ligacoes_cobranca.all():
        candidatos.append(('ligacao', l.data_hora, l.atendeu))
    if not candidatos:
        return None
    canal, quando, atendeu = max(candidatos, key=lambda c: c[1])
    out = {'canal': canal, 'quando': quando.isoformat()}
    if canal == 'ligacao':
        out['atendeu'] = atendeu
    return out


def _fila_item(evento, cfg, etapas_ativas, rotulos_map, maior_dias_ativa, hoje):
    saldo = max(evento.valor_total - evento.sinal_pago, 0)
    telefone = evento.telefone_display
    pausa = pausa_vigente(evento, hoje)
    dias_para_evento = (evento.data_evento - hoje).days

    fase = _fase_evento(evento, cfg, etapas_ativas, maior_dias_ativa, pausa, hoje)
    proxima = _proxima_acao(evento, etapas_ativas, rotulos_map, pausa, hoje, dias_para_evento)
    total_ligacoes = len(list(evento.ligacoes_cobranca.all()))

    if pausa and pausa.pausado_ate == hoje:
        rank = 0
    else:
        rank = _RANK_FASE.get(fase['codigo'], 6)

    return {
        'evento_id': evento.id, 'numero': evento.numero, 'cliente_id': evento.cliente_id,
        'nome': evento.nome_cliente_display, 'tipo_evento': evento.get_tipo_evento_display(),
        'data_evento': evento.data_evento.isoformat(), 'status': evento.status,
        'valor_total': str(evento.valor_total), 'valor_pago': str(evento.sinal_pago), 'saldo': str(saldo),
        'dias_para_evento': dias_para_evento,
        'telefone': telefone, 'sem_telefone': not bool(telefone),
        'fase': fase,
        'etapas': _etapas_payload(evento, etapas_ativas, rotulos_map, hoje),
        'pausa_vigente': (
            {'id': pausa.id, 'pausado_ate': pausa.pausado_ate.isoformat(), 'motivo': pausa.motivo}
            if pausa else None
        ),
        'ultimo_contato': _ultimo_contato(evento),
        'proxima_acao': proxima,
        'total_ligacoes': total_ligacoes,
        '_ordem': (rank, evento.data_evento.isoformat()),
    }


def _bate_filtro_fase(item, fase_filtro, hoje):
    codigo = item['fase']['codigo']
    if fase_filtro == 'lembrete':
        return codigo in ('lembrete', 'aguardando')
    if fase_filtro == 'cobranca':
        return codigo in ('cobranca', 'concluida')
    if fase_filtro == 'pausado':
        return item['pausa_vigente'] is not None
    if fase_filtro == 'prazo_hoje':
        return item['pausa_vigente'] is not None and item['pausa_vigente']['pausado_ate'] == hoje.isoformat()
    if fase_filtro == 'pos_evento':
        return item['dias_para_evento'] < 0
    if fase_filtro == 'sem_ligacao':
        return item['total_ligacoes'] == 0 and codigo != 'aguardando'
    return True


class FilaCobrancaView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        cfg = ConfiguracaoCobranca.get()
        hoje = timezone.localdate()
        etapas_ativas = list(EtapaRegua.objects.filter(ativo=True).order_by('dias'))
        rotulos_map = rotulos(etapas_ativas, cfg.limite_lembrete) if etapas_ativas else {}
        maior_dias_ativa = max((e.dias for e in etapas_ativas), default=None)

        eventos = (
            eventos_elegiveis()
            .prefetch_related('envios_cobranca', 'pausas_cobranca', 'ligacoes_cobranca')
        )
        evento_id = request.query_params.get('evento')
        if evento_id:
            eventos = eventos.filter(id=evento_id)

        itens = [_fila_item(e, cfg, etapas_ativas, rotulos_map, maior_dias_ativa, hoje) for e in eventos]

        fase_filtro = request.query_params.get('fase')
        if fase_filtro:
            itens = [i for i in itens if _bate_filtro_fase(i, fase_filtro, hoje)]

        search = (request.query_params.get('search') or '').strip().lower()
        if search:
            itens = [i for i in itens if search in i['nome'].lower() or search in i['numero'].lower()]

        itens.sort(key=lambda i: i['_ordem'])
        for i in itens:
            i.pop('_ordem', None)

        return Response(itens)


class LinhaDoTempoView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, evento_id):
        evento = get_object_or_404(Evento, pk=evento_id)
        cfg = ConfiguracaoCobranca.get()
        hoje = timezone.localdate()
        etapas_ativas = list(EtapaRegua.objects.filter(ativo=True).order_by('dias'))
        rotulos_map = rotulos(etapas_ativas, cfg.limite_lembrete) if etapas_ativas else {}

        itens = []
        for envio in evento.envios_cobranca.select_related('etapa').all():
            detalhe = ''
            if envio.status == 'pulada':
                detalhe = envio.get_motivo_pulada_display()
            itens.append({
                'tipo': 'envio', 'data_hora': envio.criado_em.isoformat(),
                'titulo': f'{envio.get_tipo_display()} {envio.rotulo_etapa or ""} — {envio.get_status_display()}'.strip(),
                'detalhe': detalhe,
                'mensagem': envio.mensagem_renderizada or None,
            })

        for ligacao in evento.ligacoes_cobranca.all():
            detalhe = f'Atendente: {ligacao.atendente_nome} · {ligacao.telefone_discado}'
            if ligacao.prazo_pagamento:
                detalhe += f'\nPrazo combinado: {ligacao.prazo_pagamento.strftime("%d/%m/%Y")}'
            if ligacao.observacao:
                detalhe += f'\nObs.: {ligacao.observacao}'
            itens.append({
                'tipo': 'ligacao', 'data_hora': ligacao.data_hora.isoformat(),
                'titulo': f'Ligação · {"atendeu" if ligacao.atendeu else "não atendeu"}',
                'detalhe': detalhe, 'autor': ligacao.atendente_nome,
            })

        for pausa in evento.pausas_cobranca.all():
            itens.append({
                'tipo': 'pausa', 'data_hora': pausa.criado_em.isoformat(),
                'titulo': f'Pausado até {pausa.pausado_ate.strftime("%d/%m/%Y")}',
                'detalhe': f'{pausa.motivo}\npor {pausa.criado_por_nome} ({pausa.get_origem_display()})',
                'autor': pausa.criado_por_nome,
            })
            if pausa.encerrada_em:
                itens.append({
                    'tipo': 'pausa_encerrada', 'data_hora': pausa.encerrada_em.isoformat(),
                    'titulo': 'Pausa encerrada antes do prazo',
                    'detalhe': f'{pausa.motivo_encerramento}\npor {pausa.encerrada_por_nome}',
                    'autor': pausa.encerrada_por_nome,
                })

        for pagamento in evento.pagamentos.filter(status='pago'):
            dh = datetime.combine(pagamento.data_pagamento, dtime.min)
            itens.append({
                'tipo': 'pagamento', 'data_hora': dh.isoformat(),
                'titulo': f'Pagamento recebido — R$ {pagamento.valor}',
                'detalhe': pagamento.get_forma_pagamento_display(),
            })

        itens.sort(key=lambda i: i['data_hora'], reverse=True)

        saldo = max(evento.valor_total - evento.sinal_pago, 0)
        pausa_atual = pausa_vigente(evento, hoje)

        return Response({
            'evento': {
                'id': evento.id, 'numero': evento.numero, 'nome': evento.nome_cliente_display,
                'tipo_evento': evento.get_tipo_evento_display(), 'data_evento': evento.data_evento.isoformat(),
                'valor_total': str(evento.valor_total), 'valor_pago': str(evento.sinal_pago), 'saldo': str(saldo),
                'telefone': evento.telefone_display,
            },
            'pausa_vigente': (
                {'id': pausa_atual.id, 'pausado_ate': pausa_atual.pausado_ate.isoformat(), 'motivo': pausa_atual.motivo}
                if pausa_atual else None
            ),
            'etapas': _etapas_payload(evento, etapas_ativas, rotulos_map, hoje),
            'linha_do_tempo': itens,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Logs de envio (só leitura)
# ─────────────────────────────────────────────────────────────────────────────

class EnvioCobrancaViewSet(CsrfExemptMixin, viewsets.ReadOnlyModelViewSet):
    queryset = EnvioCobranca.objects.select_related('evento', 'etapa').all()
    serializer_class = EnvioCobrancaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('evento'):
            qs = qs.filter(evento_id=p['evento'])
        if p.get('tipo'):
            qs = qs.filter(tipo=p['tipo'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('data_inicio'):
            qs = qs.filter(criado_em__date__gte=p['data_inicio'])
        if p.get('data_fim'):
            qs = qs.filter(criado_em__date__lte=p['data_fim'])
        return qs


# ─────────────────────────────────────────────────────────────────────────────
# Ligações (imutável — sem PATCH/PUT/DELETE)
# ─────────────────────────────────────────────────────────────────────────────

class LigacaoCobrancaViewSet(
    CsrfExemptMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = LigacaoCobranca.objects.select_related('evento', 'atendente', 'registrado_por').all()
    serializer_class = LigacaoCobrancaSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('evento'):
            qs = qs.filter(evento_id=p['evento'])
        if p.get('atendente'):
            qs = qs.filter(atendente_id=p['atendente'])
        if p.get('atendeu') not in (None, ''):
            qs = qs.filter(atendeu=p['atendeu'].lower() in ('1', 'true', 'sim'))
        if p.get('data_inicio'):
            qs = qs.filter(data_hora__date__gte=p['data_inicio'])
        if p.get('data_fim'):
            qs = qs.filter(data_hora__date__lte=p['data_fim'])
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        whatsapp_enviado = self._criar_ligacao(serializer)
        data = dict(serializer.data)
        data['whatsapp_enviado'] = whatsapp_enviado
        return Response(data, status=status.HTTP_201_CREATED)

    def _criar_ligacao(self, serializer):
        usuario = self.request.user
        validated = dict(serializer.validated_data)
        pausar = validated.pop('pausar', True)
        atendente = validated.pop('atendente', None) or usuario

        whatsapp_enviado = False
        pausa_criada = None

        with transaction.atomic():
            ligacao = LigacaoCobranca.objects.create(
                **validated, atendente=atendente, atendente_nome=atendente.name,
                registrado_por=usuario, registrado_por_nome=usuario.name,
            )
            serializer.instance = ligacao

            if ligacao.atendeu and ligacao.prazo_pagamento and pausar:
                vigente = pausa_vigente(ligacao.evento, timezone.localdate())
                if vigente:
                    vigente.encerrada_em = timezone.now()
                    vigente.encerrada_por = usuario
                    vigente.encerrada_por_nome = usuario.name
                    vigente.motivo_encerramento = 'Substituída por nova pausa'
                    vigente.save()
                pausa_criada = PausaCobranca.objects.create(
                    evento=ligacao.evento, pausado_ate=ligacao.prazo_pagamento,
                    motivo=ligacao.observacao or 'Prazo combinado por telefone',
                    origem='ligacao', ligacao=ligacao,
                    criado_por=usuario, criado_por_nome=usuario.name,
                )

            if not ligacao.atendeu:
                cfg = ConfiguracaoCobranca.get()
                saldo = max(ligacao.evento.valor_total - ligacao.evento.sinal_pago, 0)
                if cfg.ativo and cfg.msg_ligacao_nao_atendida_ativo and saldo > 0:
                    ctx = montar_contexto(ligacao.evento, cfg, timezone.localdate())
                    mensagem = render(cfg.msg_ligacao_nao_atendida, ctx)
                    telefone = ligacao.evento.telefone_display
                    ok = notificar(telefone, mensagem, cliente=ligacao.evento.cliente, tipo='cobranca')
                    EnvioCobranca.objects.create(
                        evento=ligacao.evento, tipo='ligacao_nao_atendida', ligacao=ligacao,
                        data_evento_referencia=ligacao.evento.data_evento,
                        status='enviado' if ok else 'falha',
                        telefone=telefone, mensagem_renderizada=mensagem if ok else '',
                        saldo_no_envio=saldo,
                    )
                    whatsapp_enviado = ok

        registrar(
            usuario, LogAuditoria.ACAO_COBRANCA_LIGACAO_REGISTRADA,
            detalhes={'evento_numero': ligacao.evento.numero, 'atendeu': ligacao.atendeu},
            request=self.request,
        )
        if pausa_criada:
            registrar(
                usuario, LogAuditoria.ACAO_COBRANCA_PAUSADA,
                detalhes={'evento_numero': ligacao.evento.numero, 'pausado_ate': str(pausa_criada.pausado_ate)},
                request=self.request,
            )

        return whatsapp_enviado


# ─────────────────────────────────────────────────────────────────────────────
# Pausas
# ─────────────────────────────────────────────────────────────────────────────

class PausaCobrancaViewSet(
    CsrfExemptMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = PausaCobranca.objects.select_related('evento', 'criado_por', 'encerrada_por').all()
    serializer_class = PausaCobrancaSerializer
    authentication_classes = [TokenAuthentication]

    def get_permissions(self):
        if self.action in ('create', 'encerrar'):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('evento'):
            qs = qs.filter(evento_id=p['evento'])
        if p.get('vigente') == 'true':
            hoje = timezone.localdate()
            qs = qs.filter(encerrada_em__isnull=True, pausado_ate__gte=hoje)
        return qs

    def perform_create(self, serializer):
        usuario = self.request.user
        evento = serializer.validated_data['evento']
        with transaction.atomic():
            vigente = pausa_vigente(evento, timezone.localdate())
            if vigente:
                vigente.encerrada_em = timezone.now()
                vigente.encerrada_por = usuario
                vigente.encerrada_por_nome = usuario.name
                vigente.motivo_encerramento = 'Substituída por nova pausa'
                vigente.save()
            serializer.save(origem='manual', criado_por=usuario, criado_por_nome=usuario.name)

        registrar(
            usuario, LogAuditoria.ACAO_COBRANCA_PAUSADA,
            detalhes={'evento_numero': evento.numero, 'pausado_ate': str(serializer.instance.pausado_ate)},
            request=self.request,
        )

    @action(detail=True, methods=['post'])
    def encerrar(self, request, pk=None):
        pausa = self.get_object()
        hoje = timezone.localdate()
        if pausa.encerrada_em is not None or pausa.pausado_ate < hoje:
            return Response({'detail': 'Esta pausa já está encerrada ou com o prazo vencido.'}, status=400)

        serializer = EncerrarPausaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = request.user
        pausa.encerrada_em = timezone.now()
        pausa.encerrada_por = usuario
        pausa.encerrada_por_nome = usuario.name
        pausa.motivo_encerramento = serializer.validated_data['motivo']
        pausa.save()

        registrar(
            usuario, LogAuditoria.ACAO_COBRANCA_RETOMADA,
            detalhes={'evento_numero': pausa.evento.numero, 'pausa_id': pausa.id},
            request=request,
        )
        return Response(PausaCobrancaSerializer(pausa).data)
