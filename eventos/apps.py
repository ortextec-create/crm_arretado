from django.apps import AppConfig


class EventosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'eventos'
    verbose_name       = 'Eventos'

    def ready(self):
        import eventos.signals  # noqa: F401 — registra on_evento_save via @receiver
