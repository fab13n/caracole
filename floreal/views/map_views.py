from django.shortcuts import render
from django.db.models import Q
from django.db.models.functions import Now

from .. import models as m


def map(request):
    if request.user.is_anonymous:
        networks = m.Network.objects.filter(visible=True, latitude__isnull=False)
    else:
        networks = (
            m.Network.objects.filter(visible=True, latitude__isnull=False, active=True) |
            m.Network.objects.filter(
                    Q(networkmembership__valid_until__gte=Now()) | Q(networkmembership__valid_until=None),
                    visible=False,
                    networkmembership__user=request.user,
                    latitude__isnull=False,
                    active=True
            )
        ).distinct()
    network_ids = [nw.id for nw in networks]
    producers = (
        m.FlorealUser.objects.filter(
            Q(user__networkmembership__valid_until__gte=Now()) | Q(user__networkmembership__valid_until=None),
            user__networkmembership__network__in=network_ids,
            user__networkmembership__is_producer=True,
            latitude__isnull=False,
        )
        .distinct()
        .select_related("user")
    )
    user_ids = [fu.user_id for fu in producers]
    prod_to_network = m.NetworkMembership.objects \
        .filter(
            Q(valid_until__gte=Now()) | Q(valid_until=None), 
            is_producer=True, 
            network__in=network_ids,
            user__id__in=user_ids
        ) \
        .select_related("user__florealuser") \
        .values_list("user__florealuser__id", "network__id")
    return render(
        request,
        "map.html",
        {"user": request.user, "networks": networks, "producers": producers, "prod_to_network": prod_to_network}
    )
