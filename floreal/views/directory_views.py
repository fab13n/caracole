from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.db.models.functions import Lower

from .. import models as m
from .getters import get_network, get_subgroup


def dates_of_last_purchase(user_ids, network_id):
    q = (
        m.Purchase.objects.filter(user_id__in=user_ids, product__delivery__network_id=network_id)
        .values("user_id")
        .annotate(max_date=Max("modified"))
    )
    return {r["user_id"]: str(r["max_date"].date()) for r in q}


def view_directory(request, network=None, subgroup=None):
    sg = get_subgroup(subgroup)
    nw = get_network(network) or sg.network
    user = request.user

    mb = m.NetworkMembership.objects.filter(user=user, network=nw, valid_until=None).first()
    if user.is_superuser:
        subgroups = nw.networksubgroup_set.all()
        dont_list_members = False
    elif mb is None:
        raise PermissionError
    elif mb.is_staff and subgroup is None:
        subgroups = nw.networksubgroup_set.all()
        dont_list_members = False
    elif mb.is_staff:
        subgroups = None
        dont_list_members = False
    elif mb.is_subgroup_staff:
        subgroups = None
        dont_list_members = False
        if mb.subgroup != sg:
            raise PermissionError
    else:
        subgroups = None
        dont_list_members = True
        if mb.subgroup != sg:
            raise PermissionError

    members = {
        "Administrateurs": [],
        "Producteurs": [],
        "Régulateurs": [],
    }
    if not dont_list_members:
        members["Acheteurs"] = []
        members["Candidats"] = []

    q = (
        m.NetworkMembership.objects.filter(network_id=nw, valid_until=None)
        .select_related("user")
        .select_related("user__florealuser")
        .order_by(Lower("user__last_name"), Lower("user__first_name"))
    )
    last_purchases = dates_of_last_purchase([mb.user_id for mb in q], nw.id)
    for mb in q:
        if mb.user.first_name == "extra":
            continue
        elif mb.is_staff:
            cat = "Administrateurs"
        elif mb.is_producer:
            cat = "Producteurs"
        elif sg is not None and mb.subgroup != sg:
            continue
        elif mb.is_subgroup_staff:
            cat = "Régulateurs"
        elif mb.is_buyer and not dont_list_members:
            cat = "Acheteurs"
        elif mb.is_candidate and not dont_list_members:
            cat = "Candidats"
        else:
            continue
        mb.user.last_purchase_date = last_purchases.get(mb.user_id, None)
        members[cat].append(mb.user)
    vars = {"user": user, "nw": nw, "members": members, "subgroups": subgroups, "subgroup": sg.name if sg else None}
    return render(request, "directory.html", vars)


@login_required()
def view_history(request):
    purchases = m.Purchase.objects.filter(user=request.user).select_related(
        "user",
        "product",
        "product__delivery",
        "product__delivery__network",
    )
    total = 0
    networks = {}
    for pc in purchases:
        dv = pc.product.delivery
        if dv.distribution_date is not None:
            dv_name = str(dv.distribution_date) + "|" + dv.name
        else:
            dv_name = dv.name
        nw_name = pc.product.delivery.network.name
        if (nw := networks.get(nw_name)) is None:
            networks[nw_name] = nw = {"total": 0, "deliveries": {}}
        if (dvdict := nw["deliveries"].get(dv_name)) is None:
            nw["deliveries"][dv_name] = dvdict = {"total": 0, "purchases": []}
        p = pc.price
        nw["total"] += p
        dvdict["total"] += p
        total += p
        dvdict["purchases"].append(pc)
    vars = {"user": request.user, "networks": networks, "total": total}
    return render(request, "view_history.html", vars)
