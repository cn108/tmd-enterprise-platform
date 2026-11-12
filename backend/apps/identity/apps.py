from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"
    label = "identity"
    verbose_name = "Identity"

    def ready(self):
        from apps.identity import schema  # noqa: F401  # register OpenAPI auth extension
