import re
from collections import defaultdict
from datetime import datetime

from django.db.models import Q, F, Sum, Max
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import render, redirect, reverse

from villes import plus_code
from .. import models as m
from .getters import get_network, get_delivery, must_be_prod_or_staff, must_be_staff
from .message_views import editor


# Used to decode short Google "plus codes"
CENTRAL_LATITUDE = 43.5
CENTRAL_LONGITUDE = 1.5
POSITION_REGEXP = re.compile(r"([+-]?\d+(?:\.\d*)?),([+-]?\d+(?:\.\d*)?)")


def admin(request):
    if request.user.is_anonymous:
        return HttpResponseForbidden("Réservé aux administrateurs et producteurs")
    subgroup_staff_of = defaultdict(lambda: None)
    if only := request.GET.get("only"):
        raise NotImplemented
    elif request.user.is_staff:
        networks = m.Network.objects.filter(active=True)
        messages = m.AdminMessage.objects.all()
        is_network_staff = defaultdict(lambda: True)
        is_producer = defaultdict(lambda: False)
    else:
        staff_networks = m.Network.objects.filter(
            networkmembership__is_staff=True,
            active=True,
            networkmembership__user=request.user,
            networkmembership__valid_until=None,
        )
        subgroup_staff_networks = m.Network.objects.filter(
            networkmembership__is_subgroup_staff=True,
            active=True,
            networkmembership__user=request.user,
            networkmembership__valid_until=None,
        )
        prod_networks = m.Network.objects.filter(
            networkmembership__is_producer=True,
            active=True,
            networkmembership__user=request.user,
            networkmembership__valid_until=None,
        )
        networks = staff_networks | prod_networks | subgroup_staff_networks
        messages = m.AdminMessage.objects.filter(network__in=networks)
        is_network_staff = defaultdict(lambda: False)
        is_producer = defaultdict(lambda: False)
        for nw in staff_networks:
            is_network_staff[nw.id] = True
        for nw in prod_networks:
            if not is_network_staff[nw.id]:
                is_producer[nw.id] = True
        for nw in subgroup_staff_networks:
            staff_of_subgroup_ids = m.NetworkMembership.objects.filter(
                user=request.user,
                valid_until=None,
                is_subgroup_staff=True,
            ).values_list("subgroup_id", flat=True)
            subgroups = m.NetworkSubgroup.objects.filter(id__in=staff_of_subgroup_ids).values(
                "network_id",
                "id",
                "name",
            )
            for sg in subgroups:
                subgroup_staff_of[sg["network_id"]] = sg

    deliveries = (
        m.Delivery.objects.filter(network__in=networks, state__in="ABCD").select_related("producer")
    ).order_by("state", "distribution_date", "name")
    candidacies = (
        m.NetworkMembership.objects.filter(network__in=networks, is_candidate=True, valid_until=None).select_related(
            "user"
        )
    )
    deliveries_without_purchase = {
        dv.id
        for dv in m.Delivery.objects.exclude(state="E")
        .exclude(product__purchase__isnull=False)
        .order_by("distribution_date", "state", "name")
    }

    jnetworks = {}
    for nw in networks:
        jnetworks[nw.id] = {
            "id": nw.id,
            "slug": nw.slug,
            "name": nw.name,
            "candidates": [],
            "deliveries": [],
            "active_deliveries": 0,
            "is_network_staff": is_network_staff[nw.id],
            "is_producer": is_producer[nw.id],
            "subgroup_staff_of": subgroup_staff_of.get(nw.id),
            "visible": nw.visible,
            "auto_validate": nw.auto_validate,
            "messages": [msg for msg in messages if msg.network_id == nw.id],
        }

    for cd in candidacies:
        jnetworks[cd.network_id]["candidates"].append(cd.user)

    for dv in deliveries:
        jnw = jnetworks[dv.network_id]
        if not (jnw["is_network_staff"] or jnw["subgroup_staff_of"]) and dv.producer_id != request.user.id:
            continue
        jdv = {
            "id": dv.id,
            "state": dv.state,
            "state_name": dv.state_name(),
            "name": dv.name,
            "freeze_date": dv.freeze_date,
            "distribution_date": dv.distribution_date,
            "producer": dv.producer,
            "has_purchases": dv.id not in deliveries_without_purchase,
        }
        if dv.state in "BCD":
            jnw["active_deliveries"] += 1
        jnw["deliveries"].append(jdv)

    context = {
        "user": request.user,
        "messages": [msg for msg in messages if msg.network_id is None],
        "networks": jnetworks.values(),
        "Delivery": m.Delivery,
    }
    return render(request, "admin_reseaux.html", context)


def reseau(request, network):
    nw = get_network(network)
    if request.user.is_anonymous:
        mb = None
    else:
        mb = m.NetworkMembership.objects.filter(user=request.user, network=nw, valid_until=None).first()
    status = (
        "non-member"
        if mb is None
        else "member"
        if mb.is_buyer
        else "candidate"
        if mb.is_candidate
        else "non-member"
    )
    vars = {
        "network": nw,
        "user": request.user,
        "has_open_deliveries": status == "member"
        and m.Delivery.objects.filter(state=m.Delivery.ORDERING_ALL, network=nw).exists(),
        "user_status": status,
    }
    return render(request, "reseau.html", vars)


def create_network(request, nw_name):
    user = request.user
    if not user.is_staff:
        return HttpResponseForbidden("Creation de réseaux réservée au staff")
    if m.Network.objects.filter(name__iexact=nw_name).exists():
        return HttpResponseBadRequest("Il y a déjà un réseau nommé " + nw_name)
    nw = m.Network.objects.create(name=nw_name)
    m.NetworkMembership.objects.create(network=nw, user=request.user, is_staff=True)
    m.JournalEntry.log(user, "Created network nw-%d: %s", nw.id, nw_name)
    target = request.GET.get("next")
    return redirect(target) if target else redirect("network_admin", network=nw.id)


def _set_network_field(request, network, name, val):
    nw = get_network(network)
    must_be_prod_or_staff(request, nw)
    setattr(nw, name, val)
    nw.save()
    m.JournalEntry.log(request.user, "Set %s=%s in nw-%d", name, val, nw.id)
    target = request.GET.get("next")
    return redirect(target) if target else HttpResponse("")


def set_network_visibility(request, network, val):
    b = val.lower() in ("on", "true", "1")
    return _set_network_field(request, network, "visible", b)


def set_network_validation(request, network, val):
    b = val.lower() in ("on", "true", "1")
    return _set_network_field(request, network, "auto_validate", b)


def view_emails_pdf(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    from . import latex

    return latex.emails(nw)


def view_emails(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    user = request.user
    vars = {"user": user, "network": nw}
    return render(request, "emails.html", vars)


def _description_and_image(request, obj, title):
    if request.method == "POST":
        obj.description = request.POST["editor"]
        img = request.FILES.get("image")
        if img:
            obj.image_description = img
        if pos := request.POST.get("position"):
            try:
                (obj.latitude, obj.longitude) = plus_code.to_lat_lon(pos)
            except ValueError:
                if match := POSITION_REGEXP.match(pos.replace(" ", "")):
                    (obj.latitude, obj.longitude) = (float(x) for x in match.groups())
                else:
                    return HttpResponseBadRequest("Position invalide")
        if (sdescr := request.POST.get("short_description")) is not None:
            obj.short_description = sdescr
        obj.save()
        return redirect(request.GET.get("next", "admin"))
    else:
        return editor(
            request,
            title=title,
            template="description_and_image.html",
            content=obj.description,
            obj=obj,
            has_short_description=hasattr(obj, "short_description"),
        )


def network_description_and_image(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    return _description_and_image(request, nw, f"Présentation du réseau {nw.name}")


def user_description_and_image(request, user):
    flu = m.FlorealUser.objects.get(user_id=user)
    if request.user.is_staff:
        pass
    elif flu.user == request.user:
        pass
    elif m.NetworkMembership.objects.filter(
        valid_until=None,
        user=flu.user,
        is_producer=True,
        network__networkmembership__user=request.user,
        network__networkmembership__valid_until=None,
        network__networkmembership__is_staff=True,
    ).exists():
        pass
    else:
        return HttpResponseForbidden("Vous n'avez pas le droit d'éditer cette fiche")
    return _description_and_image(request, flu, f"Présentation de {flu.user.first_name} {flu.user.last_name}")


def bestof(request):
    must_be_staff(request)
    if not m.Bestof.objects.all().exists():
        m.Bestof.update()
    return render(
        request,
        "bestof.html",
        {"bestof": m.Bestof.objects.all().select_related("user"), "agg": m.Bestof.objects.aggregate(Sum("total"), Max("total"))},
    )
