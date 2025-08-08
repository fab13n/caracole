from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.template.context_processors import csrf
from django.db.models import Sum, Max, Count, Q
from django.db.models.functions import Now

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


@login_required()
def orders(request):
    networks = m.Network.objects.filter(
        networkmembership__user=request.user,
        networkmembership__is_buyer=True,
        networkmembership__valid_until=None,
        active=True,
    )
    deliveries = (
        m.Delivery.objects.filter(network__in=networks, state__in="BCD")
        .order_by("distribution_date", "name")
    )
    purchases = (
        m.Purchase.objects.filter(product__delivery__in=deliveries, user=request.user)
        .select_related("product")
    )

    messages = m.AdminMessage.objects.filter(network__in=networks).order_by("id")

    nw_by_id = {}
    dv_by_id = {}
    for nw in networks:
        jnw = {"id": nw.id, "name": nw.name, "slug": nw.slug, "messages": [], "deliveries": []}
        nw_by_id[nw.id] = jnw
    for msg in messages:
        nw_by_id[msg.network_id]["messages"].append(msg.message)
    for dv in deliveries:
        jdv = {
            "id": dv.id,
            "name": dv.name,
            "state": dv.state,
            "state_name": dv.state_name(),
            "purchases": [],
            "total_price": 0.0,
            "freeze": dv.freeze_date,
            "distribution": dv.distribution_date,
        }
        dv_by_id[dv.id] = jdv
        nw_by_id[dv.network_id]["deliveries"].append(jdv)
    for pc in purchases:
        pd = pc.product
        jdv = dv_by_id[pd.delivery_id]
        jpc = {
            "pd_id": pd.id,
            "name": pd.name,
            "unit": pd.unit,
            "quantity": float(pc.quantity),
            "price": float(pc.price),
        }
        jdv["purchases"].append(jpc)
        jdv["total_price"] += float(pc.price)
    active_networks = [jnw for jnw in nw_by_id.values() if jnw["messages"] or jnw["deliveries"]]
    context = {
        "user": request.user,
        "Delivery": m.Delivery,
        "networks": active_networks,
        "general_messages": [msg.message for msg in m.AdminMessage.objects.filter(network=None)],
    }
    return render(request, "orders.html", context)


@login_required()
def order(request):
    vars = {}
    return render(request, "order.html", vars)


@login_required()
def user(request):
    vars = {
        "bestof": m.Bestof.objects.filter(user=request.user).first(),
        "agg": m.Bestof.objects.aggregate(Sum("total"), Max("total"), Count("total")),
    }
    return render(request, "user.html", vars)


def map(request):
    if request.user.is_anonymous:
        networks = m.Network.objects.filter(visible=True, latitude__isnull=False)
    else:
        networks = (
            m.Network.objects.filter(visible=True, latitude__isnull=False) |
            m.Network.objects.filter(
                    Q(networkmembership__valid_until__gte=Now()) | Q(networkmembership__valid_until=None),
                    visible=False,
                    networkmembership__user=request.user,
                    latitude__isnull=False,
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
