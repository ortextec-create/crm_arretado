from django.apps import AppConfig


class PedidosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "pedidos"
    verbose_name       = "Pedidos Unificados"

    def ready(self):
        """Registra signals assim que o app é carregado."""
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from ifood.models import PedidoIFood
        from .models import sincronizar_pedido_ifood

        @receiver(post_save, sender=PedidoIFood)
        def on_pedido_ifood_save(sender, instance, **kwargs):
            try:
                sincronizar_pedido_ifood(instance)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Falha ao sincronizar PedidoUnificado para iFood #%s: %s",
                    instance.pk, e,
                )

        import pdv.signals      # noqa: F401
        #import eventos.signals  # noqa: F401  ← LINHA NOVA