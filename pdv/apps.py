from django.apps import AppConfig


class PdvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'pdv'
    verbose_name       = 'PDV Próprio'

    def ready(self):
        import pdv.signals  # noqa: F401
