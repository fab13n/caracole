from django.core.management.base import BaseCommand
from ... import models as m


class Command(BaseCommand):
    help = "Migration de septembre 2021, depuis Caracole et Solalim"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        destroyed_network_names = "ovalie bougnol ariège aude lozère".split()
        hidden_network_names = "test hangar haute-garonne gloire lauragais".split()
        q = m.Network.objects.none()
        for n in destroyed_network_names:
            q |= m.Network.objects.filter(name__icontains=n)
        print("deleting", q)
        q.delete()
        q = m.Network.objects.none()
        for n in hidden_network_names:
            q |= m.Network.objects.filter(name__icontains=n)
        print("hiding", q)
        q.update(visible=False)
        