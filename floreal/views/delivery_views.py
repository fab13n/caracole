from collections import defaultdict
from datetime import datetime

from django.db.models import Q, F
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, reverse

from .. import models as m
from .getters import get_network, get_delivery, must_be_prod_or_staff, must_be_staff


def _dv_has_no_purchase(dv):
    return not m.Purchase.objects.filter(product__delivery=dv).exists()


def archived_deliveries(request, network):
    must_be_prod_or_staff(request, network)
    user = request.user
    nw = get_network(network)
    vars = {
        "user": user,
        "nw": nw,
        "Delivery": m.Delivery,
        "deliveries": m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)
        .order_by(F("distribution_date").desc(nulls_last=True), "name"),
    }
    vars["empty_deliveries"] = (
        vars["deliveries"].filter(product__purchase__isnull=True).distinct().order_by("-distribution_date", "name")
    )
    return render(request, "archived_deliveries.html", vars)


def delete_archived_delivery(request, delivery):
    dv = get_delivery(delivery)
    must_be_prod_or_staff(request, dv.network)
    if not _dv_has_no_purchase(dv):
        return HttpResponseForbidden("Cette commande n'est pas vide, passer par l'admin DB")
    nw = dv.network
    m.JournalEntry.log(
        request.user,
        "Deleting archived delivery dv-%d (%s) from %s",
        dv.id,
        dv.name,
        nw.name,
    )
    dv.delete()
    target = request.GET.get("next")
    return redirect(target) if target else redirect("archived_deliveries", nw.id)


def delete_all_archived_deliveries(request, network):
    nw = get_network(network)
    must_be_prod_or_staff(request, nw)
    deliveries = m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)
    ids = []
    for dv in deliveries:
        if _dv_has_no_purchase(dv):
            ids.append(dv.id)
            dv.delete()
    m.JournalEntry.log(
        request.user,
        "Deleted archived empty deliveries [%s] from %s",
        ", ".join("dv-%d" % i for i in ids),
        nw.name,
    )
    target = request.GET.get("next")
    return redirect(target) if target else redirect("archived_deliveries", network)


def list_delivery_models(request, network, all_networks=False):
    """Propose to create a delivery based on a previous delivery."""
    nw = m.Network.objects.get(id=network)
    if all_networks:
        if request.user.is_staff:
            authorized_networks = m.Network.objects.filter(active=True)
        else:
            authorized_networks = m.Network.objects.filter(
                networkmembership__is_staff=True,
                networkmembership__user=request.user,
                networkmembership__valid_until=None,
            )
        deliveries = m.Delivery.objects.filter(network__in=authorized_networks).select_related("network")
        which = "staff"
    else:
        which = must_be_prod_or_staff(request, nw)
        deliveries = m.Delivery.objects.filter(network=nw)
        if which == "producer":
            deliveries = deliveries.filter(producer_id=request.user.id)

    deliveries = deliveries.filter(Q(product__isnull=False) | Q(description__isnull=False)).distinct()

    vars = {
        "user": request.user,
        "nw": nw,
        "all_networks": all_networks,
        "producer": request.user if which == "producer" else None,
        "deliveries": deliveries.order_by("network", "-id"),
    }
    return render(request, "list_delivery_models.html", vars)


def create_delivery(request, network, dv_model=None):
    if dv_model:
        dv_model = m.Delivery.objects.get(id=dv_model)
    else:
        dv_model = None

    nw = get_network(network)
    which = must_be_prod_or_staff(request, nw)
    if which == "producer" and dv_model and dv_model.producer_id != request.user.id:
        return HttpResponseForbidden("Les producteurs ne peuvent cloner que leurs propres commandes")

    if dv_model is not None:
        prod_id = dv_model.producer_id
        if (
            prod_id is not None
            and dv_model.network_id != nw.id
            and not m.NetworkMembership.objects.filter(
                network=nw,
                valid_until=None,
                is_producer=True,
                user_id=prod_id,
            ).exists()
        ):
            prod_id = None

        new_dv = m.Delivery.objects.create(
            name=dv_model.name,
            network=nw,
            state=m.Delivery.PREPARATION,
            producer_id=prod_id,
            description=dv_model.description,
        )
        for pd in dv_model.product_set.all():
            pd.pk = None
            pd.delivery_id = new_dv.id
            pd.quantity_limit = None
            pd.save()
    else:
        now = datetime.now()
        months = "Janvier Février Mars Avril Mai Juin Juillet Août Septembre Octobre Novembre Décembre".split()

        name = "%s %d" % (months[now.month - 1], now.year)
        fmt = "%dème de " + name
        n = 1
        while m.Delivery.objects.filter(network=nw, name=name).exists():
            n += 1
            name = fmt % n
        new_dv = m.Delivery.objects.create(
            name=name,
            network=nw,
            state=m.Delivery.PREPARATION,
            producer_id=request.user.id if which == "producer" else None,
        )

    m.JournalEntry.log(
        request.user,
        "Created new delivery dv-%d %s in nw-%d %s",
        new_dv.id,
        new_dv.name,
        nw.id,
        nw.name,
    )
    return redirect(reverse("edit_delivery_products", kwargs={"delivery": new_dv.id}))


def set_delivery_state(request, delivery, state):
    dv = get_delivery(delivery)
    must_be_prod_or_staff(request, dv.network)
    if state not in m.Delivery.STATE_CHOICES:
        return HttpResponseBadRequest(state + " n'est pas un état valide.")
    dv.state = state
    if state >= m.Delivery.FROZEN and dv.freeze_date is None:
        dv.freeze_date = m.TruncDate(m.Now())
    dv.save()
    m.JournalEntry.log(request.user, "Set state=%s in dv-%d", state, dv.id)

    target = request.GET.get("next")
    return redirect(target) if target else HttpResponse("")


def set_delivery_name(request, delivery, name):
    dv = get_delivery(delivery)
    must_be_prod_or_staff(request, dv.network)
    prev_name = dv.name
    dv.name = name
    dv.save()
    m.JournalEntry.log(
        request.user,
        "Change delivery dv-%d name in nw-%d %s: %s->%s",
        dv.id,
        dv.network.id,
        dv.network.name,
        prev_name,
        name,
    )
    return HttpResponse("")


def active_products(request):
    products = m.Product.objects.filter(
        delivery__network__networkmembership__is_buyer=True,
        delivery__state__in="BDC",
        delivery__network__networkmembership__user=request.user,
        delivery__network__networkmembership__valid_until=None,
    )
    d = defaultdict(list)
    for pd in products:
        d[pd.delivery_id].append({"id": pd.id, "name": pd.name, "price": pd.price, "unit": pd.unit})
    return JsonResponse(d)
