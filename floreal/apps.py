from django.apps import AppConfig

class TasksConfig(AppConfig):
    name = 'floreal'
    verbose_name = "Floreal"

    def ready(self):
        from .signals import handlers  # noqa
