from django.apps import AppConfig


class PedidosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'pedidos'
    verbose_name       = 'Pedidos Unificados'

    def ready(self):
        """Registra signals assim que o app é carregado."""
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from ifood.models import PedidoIFood
        from .models import sincronizar_pedido_ifood

        @receiver(post_save, sender=PedidoIFood)
        def on_pedido_ifood_save(sender, instance, **kwargs):
            """
            Sempre que um PedidoIFood for criado ou atualizado,
            espelha os dados no PedidoUnificado.
            """
            try:
                sincronizar_pedido_ifood(instance)
            except Exception as e:
                # Nunca deixa o signal quebrar o fluxo principal
                import logging
                logging.getLogger(__name__).warning(
                    'Falha ao sincronizar PedidoUnificado para iFood #%s: %s',
                    instance.pk, e,
                )
