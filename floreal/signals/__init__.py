import django.dispatch

task_generate_pre_save = django.dispatch.Signal(providing_args=["task"])
