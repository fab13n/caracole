from django.apps import AppConfig


class CustomizeWagtailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customize_wagtail'
