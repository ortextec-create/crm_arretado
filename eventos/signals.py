"""
Signal: espelha Evento → PedidoUnificado automaticamente no post_save.
Registrado em EventosConfig.ready() via eventos/apps.py.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Evento


@receiver(post_save, sender=Evento)
def on_evento_save(sender, instance, **kwargs):
    """
    Sempre que um Evento for criado ou atualizado,
    espelha os dados no PedidoUnificado.
    Nunca falha o fluxo principal.
    """
    try:
        from .models import sincronizar_evento
        sincronizar_evento(instance)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            'Falha ao sincronizar PedidoUnificado para Evento #%s: %s',
            instance.pk, e,
        )
