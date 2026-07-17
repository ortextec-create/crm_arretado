from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('api/v1/', include('clientes.urls')),
    path('api/v1/', include('usuarios.urls')),
    path('api/v1/auditoria/', include('auditoria.urls')),
    path('api/v1/', include('pedidos.urls')),
    path('api/v1/ifood/', include('ifood.urls')),
    path('api/v1/pdv/', include('pdv.urls')),
    path('api/v1/eventos/', include('eventos.urls')),
    path('api/v1/notificacoes/', include('notificacoes.urls')),
    path('api/v1/fichas/',       include('fichas.urls')),
    path('api/v1/estoque/',      include('estoque.urls')),
    path('api/v1/relatorios/',   include('relatorios.urls')),
    path('api/v1/dashboard/',    include('dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
