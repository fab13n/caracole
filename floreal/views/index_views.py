from django.shortcuts import render
from django.template.context_processors import csrf

from pages.models import TexteDAccueil
from .. import models as m


def index(request):
    try:
        accueil = (
            TexteDAccueil.objects.all().values("texte_accueil").first()["texte_accueil"]
        )
    except AttributeError:
        accueil = "Penser à renseigner le texte d'accueil :-)"
    if request.user.is_anonymous:
        vars = {
            "networks": m.Network.objects.exclude(visible=False).exclude(active=False),
            "accueil": accueil,
        }
        vars.update(csrf(request))
        return render(request, "index_unlogged.html", vars)
    else:
        mbships = list(
            m.NetworkMembership.objects.filter(
                user=request.user,
                valid_until=None,
                network__active=True,
            ).prefetch_related("network", "network__ville")
        )
        networks_with_open_orders = {
            nw["id"]
            for nw in m.Network.objects.filter(
                id__in=[mb.network_id for mb in mbships],
                delivery__state=m.Delivery.ORDERING_ALL,
            )
            .distinct()
            .values("id")
        }
        for nm in mbships:
            nm.has_open_orders = nm.is_buyer and nm.network_id in networks_with_open_orders
        number_of_deliveries = m.Delivery.objects.filter(
            state=m.Delivery.ORDERING_ALL,
            network__networkmembership__user=request.user,
            network__networkmembership__valid_until=None,
            network__networkmembership__is_buyer=True,
        ).count()
        vars = {
            "user": request.user,
            "accueil": accueil,
            "number_of_deliveries": number_of_deliveries,
            "memberships": mbships,
            "unsubscribed": m.Network.objects.exclude(members=request.user)
            .exclude(visible=False)
            .exclude(active=False)
            .prefetch_related("ville"),
        }
        return render(request, "index_logged.html", vars)
