from rest_framework.routers import DefaultRouter
from django.urls import path
from . import views

router = DefaultRouter()
router.register('materias-primas', views.MateriaPrimaViewSet)
router.register('fichas',          views.FichaTecnicaViewSet)
router.register('parametros',      views.ParametrosNegocioViewSet, basename='parametros')
router.register('snapshots',       views.SnapshotPrecosViewSet)

urlpatterns = router.urls + [
    path('ajuste-linear/',                          views.AjusteLinearView.as_view()),
    path('desfazer-ajuste/<int:snapshot_id>/',      views.DesfazerAjusteView.as_view()),
]
