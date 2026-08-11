from rest_framework import views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .versao import obter_versao


class CsrfExemptMixin:
    authentication_classes = []


class VersaoView(CsrfExemptMixin, views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(obter_versao())
