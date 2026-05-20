from django.db.models import Q
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import Cliente, Endereco, TagCliente
from .serializers import (
    ClienteListSerializer, ClienteDetailSerializer,
    EnderecoSerializer, TagSerializer
)


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.prefetch_related('enderecos', 'tags').all()
    permission_classes = [AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nome', 'criado_em', 'atualizado_em', 'status']
    ordering = ['-criado_em']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClienteListSerializer
        return ClienteDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Busca geral
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(nome__icontains=search) |
                Q(cpf__icontains=search) |
                Q(email__icontains=search) |
                Q(telefone_principal__icontains=search)
            )

        # Filtros específicos
        status_filter = params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        cidade = params.get('cidade')
        if cidade:
            qs = qs.filter(enderecos__cidade__icontains=cidade)

        tag_id = params.get('tag')
        if tag_id:
            qs = qs.filter(tags__id=tag_id)

        # Filtros de integração
        com_ifood = params.get('com_ifood')
        if com_ifood == 'true':
            qs = qs.exclude(ifood_customer_id__isnull=True).exclude(ifood_customer_id='')
        elif com_ifood == 'false':
            qs = qs.filter(Q(ifood_customer_id__isnull=True) | Q(ifood_customer_id=''))

        return qs.distinct()

    @action(detail=True, methods=['post'], url_path='enderecos')
    def adicionar_endereco(self, request, pk=None):
        cliente = self.get_object()
        serializer = EnderecoSerializer(data=request.data, context={'cliente': cliente, 'request': request})
        if serializer.is_valid():
            serializer.save(cliente=cliente)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='enderecos/(?P<endereco_id>[^/.]+)')
    def atualizar_endereco(self, request, pk=None, endereco_id=None):
        cliente = self.get_object()
        try:
            endereco = cliente.enderecos.get(pk=endereco_id)
        except Endereco.DoesNotExist:
            return Response({'detail': 'Endereço não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = EnderecoSerializer(endereco, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='enderecos/(?P<endereco_id>[^/.]+)/remover')
    def remover_endereco(self, request, pk=None, endereco_id=None):
        cliente = self.get_object()
        try:
            endereco = cliente.enderecos.get(pk=endereco_id)
        except Endereco.DoesNotExist:
            return Response({'detail': 'Endereço não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        endereco.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='bloquear')
    def bloquear(self, request, pk=None):
        cliente = self.get_object()
        cliente.status = 'bloqueado'
        cliente.save(update_fields=['status', 'atualizado_em'])
        return Response({'status': 'bloqueado'})

    @action(detail=True, methods=['post'], url_path='ativar')
    def ativar(self, request, pk=None):
        cliente = self.get_object()
        cliente.status = 'ativo'
        cliente.save(update_fields=['status', 'atualizado_em'])
        return Response({'status': 'ativo'})

    @action(detail=False, methods=['get'], url_path='estatisticas')
    def estatisticas(self, request):
        total = Cliente.objects.count()
        ativos = Cliente.objects.filter(status='ativo').count()
        inativos = Cliente.objects.filter(status='inativo').count()
        bloqueados = Cliente.objects.filter(status='bloqueado').count()
        com_ifood = Cliente.objects.exclude(ifood_customer_id__isnull=True).exclude(ifood_customer_id='').count()
        com_anotaai = Cliente.objects.exclude(anotaai_customer_id__isnull=True).exclude(anotaai_customer_id='').count()
        return Response({
            'total': total,
            'ativos': ativos,
            'inativos': inativos,
            'bloqueados': bloqueados,
            'com_ifood': com_ifood,
            'com_anotaai': com_anotaai,
        })


class TagViewSet(viewsets.ModelViewSet):
    queryset = TagCliente.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
