from django.apps import AppConfig


class CaveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cave"
    verbose_name = "Gestion de la cave"

    def ready(self):
        # Branche l'enregistrement des connexions dans le journal du patron
        from . import signaux  # noqa: F401
