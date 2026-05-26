from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('clientes.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/v1/ifood/', include('ifood.urls')),
    path('api/v1/pdv/',    include('pdv.urls')),   # ← ADICIONAR
    path('api/v1/', include('pedidos.urls')),   # ← FASE 4: adicionar esta linha


]
