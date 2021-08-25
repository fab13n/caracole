#!/usr/bin/python3

from datetime import datetime
import os
import re
from collections import defaultdict
from django.db.models.query_utils import select_related_descend
from django.http.response import JsonResponse

from django.conf import settings
from django.shortcuts import render, redirect, reverse
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import html
from django.template.context_processors import csrf, request
from django.db.models import Count, Q
from openlocationcode import openlocationcode

from villes import plus_code
from home.models import HomePage

from .. import models as m
from .getters import get_network, get_delivery
from .decorators import nw_admin_required, regulator_required

from .edit_delivery_purchases import edit_delivery_purchases
from .buy import buy
from .user_registration import user_register, user_update, user_deactivate
from .edit_delivery_products import edit_delivery_products, delivery_products_json
from .view_purchases import (
    view_purchases_html,
    view_purchases_latex_table,
    view_purchases_xlsx,
    view_purchases_latex_cards,
    view_purchases_json,
    get_archive,
    all_deliveries_html,
    all_deliveries_latex,
)
from .spreadsheet import spreadsheet
from .candidacies import (
    candidacy,
    cancel_candidacy,
    validate_candidacy,
    leave_network,
    create_candidacy,
    manage_candidacies,
)
from .invoice_mail import invoice_mail_form
from .users import users_json, users_html
from . import delivery_description as dd


def index(request):
    accueil = HomePage.objects.all().first().texte_accueil
    if request.user.is_anonymous:
        my_networks = list()
        vars = {"networks": m.Network.objects.exclude(visible=False), "accueil": accueil}
        vars.update(csrf(request))
        return render(request, "index_unlogged.html", vars)
    else:
        mbships = list(m.NetworkMembership.objects
            .filter(user=request.user, valid_until=None)
        )
        for nm in mbships:
            hoo = (
                nm.is_buyer
                # TODO can be performed into a single query with network_id__in
                and m.Delivery.objects.filter(
                    network_id=nm.network_id, state=m.Delivery.ORDERING_ALL
                ).exists()
            )
            nm.has_open_orders = hoo

        vars = {
            "user": request.user,
            "accueil": accueil,
            "memberships": mbships,
            "unsubscribed": m.Network.objects \
                .exclude(members=request.user) \
                .exclude(visible=False)
        }
        return render(request, "index_logged.html", vars)


def admin(request):
    if (only := request.GET.get('only')):
        networks = m.Network.objects.filter(
            id=only,
            networkmembership__user=request.user,
            networkmembership__is_staff=True,
            networkmembership__valid_until=None,
        )
    elif request.user.is_staff:
        networks = m.Network.objects.all()
    else:
        networks = (m.Network.objects
            .filter(networkmembership__user=request.user,
                    networkmembership__is_staff=True,
                    networkmembership__valid_until=None)
        )
    deliveries = (m.Delivery.objects
        .filter(network__in=networks, state__in="ABCD")
        .select_related("producer")
    )

    candidacies = (m.NetworkMembership.objects
        .filter(network__in=networks,
                is_candidate=True,
                valid_until=None)
        .select_related("user")
    )

    jnetworks = {}

    for nw in networks:
        jnetworks[nw.id] = {
            "id": nw.id,
            "slug": nw.slug,
            "name": nw.name,
            "candidates": [],
            "deliveries": [],
            "active_deliveries": 0,
            "is_network_staff": True  # will change for producers
        }

    for cd in candidacies:
        jnetworks[cd.network_id]["candidates"].append(cd.user)

    for dv in deliveries:
        jdv = {
            "id": dv.id,
            "state": dv.state,
            "state_name": dv.state_name(),
            "name": dv.name,
            "freeze_date": dv.freeze_date,
            "distribution_date": dv.distribution_date,
            "producer": dv.producer
        }
        jnw = jnetworks[dv.network_id]
        if dv.state in "BCD":
            jnw["active_deliveries"] += 1
        jnw["deliveries"].append(jdv)

    context = {
        "user": request.user,
        "messages": m.AdminMessage.objects.filter(network=None),
        "networks": jnetworks.values(),
        "Delivery": m.Delivery,
    }
    
    return render(request, "admin_reseaux.html", context)

@login_required()
def orders(request):
    networks = [
        mb.network
        for mb in m.NetworkMembership.objects
        .filter(user=request.user, is_buyer=True, valid_until=None)
        .select_related("network")
        .only("network")
    ]
    deliveries = (m.Delivery.objects
        .filter(network__in=networks)
        .filter(state__in="BCD")
    )
    purchases = (m.Purchase.objects
        .filter(product__delivery__in=deliveries)
        .filter(user=request.user)
        .select_related("product")
    )
    messages = (m.AdminMessage.objects
        .filter(network__in=networks)
    )

    nw_by_id = {}
    dv_by_id = {}
 
    for nw in networks:
        jnw = {
            "id": nw.id,
            "name": nw.name,
            "slug": nw.slug,
            "messages": [],
            "deliveries": [],
        } 
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
            "total_price": 0.,
            "freeze": dv.freeze_date,
            "distribution": dv.distribution_date,
        }
        dv_by_id[dv.id] = jdv
        nw_by_id[dv.network_id]['deliveries'].append(jdv)

    for pc in purchases:
        pd = pc.product
        jdv = dv_by_id[pd.delivery_id]
        jpc = {
            "name": pd.name,
            "unit": pd.unit,
            "quantity": float(pc.quantity),
            "price": float(pc.price)
        }
        jdv["purchases"].append(jpc)
        jdv["total_price"] += float(pc.price)

    active_networks = [jnw
        for jnw in nw_by_id.values()
        if jnw['messages'] or jnw['deliveries']
    ]
    context = {
        "user": request.user,
        "Delivery": m.Delivery,
        "networks": active_networks,
        "general_messages": [msg.message for msg in m.AdminMessage.objects.filter(network=None)]
    }
    return render(request, "orders.html", context)


@login_required()
def order(request):
    vars = {}
    return render(request, "order.html", vars)


@login_required()
def user(request):
    vars = {}
    return render(request, "user.html", vars)


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
        and m.Delivery.objects.filter(state=m.Delivery.ORDERING_ALL).exists(),
        "user_status": status,
    }
    return render(request, "reseau.html", vars)



@nw_admin_required()
def network_admin(request, network):
    user = request.user
    nw = get_network(network)
    vars = {
        "user": user,
        "nw": nw,
        "deliveries": m.Delivery.objects.filter(network=nw).exclude(
            state=m.Delivery.TERMINATED
        ),
        "Delivery": m.Delivery,
    }
    return render(request, "network_admin.html", vars)


def producer(request, network):
    vars = {
        "Delivery": m.Delivery,
        "deliveries": m.Delivery.objects.filter(
            network_id=network,
            state__in=(
                m.Delivery.PREPARATION,
                m.Delivery.ORDERING_ALL,
                m.Delivery.ORDERING_ADMIN,
            ),
        ),
        "user": request.user,
        "network": get_network(network),
    }
    if not vars["network"].producers.filter(id=vars["user"].id).exists():
        raise ValueError("Forbidden")
    return render(request, "producer.html", vars)


def _dv_has_no_purchase(dv):
    for pd in dv.product_set.all():
        if pd.purchase_set.exists():
            return False
    return True


@nw_admin_required()
def archived_deliveries(request, network):
    user = request.user
    nw = get_network(network)
    vars = {"user": user, "nw": nw}
    vars["deliveries"] = m.Delivery.objects.filter(
        network=nw, state=m.Delivery.TERMINATED
    )
    vars["empty_deliveries"] = (
        vars["deliveries"].filter(product__purchase__isnull=True).distinct()
    )
    return render(request, "archived_deliveries.html", vars)


@nw_admin_required()
def delete_archived_delivery(request, delivery):
    dv = get_delivery(delivery)
    if not _dv_has_no_purchase(dv):
        return HttpResponseForbidden(
            "Cette commande n'est pas vide, passer par l'admin DB"
        )
    nw = dv.network
    dv.delete()
    m.JournalEntry.log(
        request.user,
        "Deleted archived delivery dv-%d (%s) from %s",
        dv.id,
        dv.name,
        nw.name,
    )
    target = request.GET.get('next')
    return redirect(target) if target else redirect("archived_deliveries", nw.id)


@nw_admin_required()
def delete_all_archived_deliveries(request, network):
    nw = get_network(network)
    deliveries = m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)
    ids = []  # For logging purposes
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
    target = request.GET.get('next')
    return redirect(target) if target else redirect("archived_deliveries", network)


def create_network(request, nw_name):
    user = request.user
    if not user.is_staff:
        return HttpResponseForbidden("Creation de réseaux réservée au staff")
    if m.Network.objects.filter(name__iexact=nw_name).exists():
        return HttpResponseBadRequest("Il y a déjà un réseau nommé " + nw_name)
    nw = m.Network.objects.create(name=nw_name)
    mb = m.NetworkMembership.objects.create(
        network=nw,
        user=request.user,
        is_staff=True
    )
    m.JournalEntry.log(user, "Created network nw-%d: %s", nw.id, nw_name)
    target = request.GET.get("next")
    return redirect(target) if target else redirect("network_admin", network=nw.id)


def edit_delivery_staff(request, delivery):
    """Edit a delivery as a full network admin: act upon its lifecycle, control which subgroups have been validated,
    change the products characteristics, change other users' orders."""
    dv = m.Delivery.objects.get(id=delivery)
    if not m.NetworkMembership.objects.filter(
        user=request.user, network=dv.network, is_staff=True, valid_until=None
    ).exists():
        HttpResponseForbidden("Réservé aux admins")
    vars = {
        "user": request.user,
        "dv": dv,
        "network": dv.network,
        "Delivery": m.Delivery,
        "steps": [
            {
                "s": s,
                "text": m.Delivery.STATE_CHOICES[s],
                "is_done": dv.state >= s,
                "is_current": dv.state == s,
            }
            for s in "ABCDE"
        ],
        "CAN_EDIT_PURCHASES": dv.state
        in [m.Delivery.ORDERING_ALL, m.Delivery.ORDERING_ADMIN],
        "CAN_EDIT_PRODUCTS": dv.state != m.Delivery.TERMINATED,
    }
    return render(request, "edit_delivery_staff.html", vars)


def list_delivery_models(request, network, all_networks=False, producer=False):
    """Propose to create a delivery based on a previous delivery."""
    nw = m.Network.objects.get(id=network)
    if all_networks:
        authorized_networks = m.Network.objects.filter(
            networkmembership__user=request.user, 
            networkmembership__is_staff=True,
            networkmembership__valid_until=None)
        deliveries = m.Delivery.objects.filter(network__in=authorized_networks)
    else:
        deliveries = m.Delivery.objects.filter(network=nw)
    if producer:
        # Producer can only use their own commands as templates
        deliveries = deliveries.filter(producer_id=request.user.id)
    vars = {
        "user": request.user,
        "nw": nw,
        "all_networks": all_networks,
        "producer": producer,
        "deliveries": deliveries.order_by("network", "-id"),
    }
    return render(request, "list_delivery_models.html", vars)


def create_delivery(request, network, dv_model=None):

    """Create a new delivery, then redirect to its edition page."""
    nw = get_network(network)

    months = [
        "Janvier",
        "Février",
        "Mars",
        "Avril",
        "Mai",
        "Juin",
        "Juillet",
        "Août",
        "Septembre",
        "Octobre",
        "Novembre",
        "Décembre",
    ]
    now = datetime.now()
    name = "%s %d" % (months[now.month - 1], now.year)
    fmt = "%dème de " + name
    n = 1
    while m.Delivery.objects.filter(network=nw, name=name).exists():
        n += 1
        name = fmt % n
    new_dv = m.Delivery.objects.create(
        name=name, network=nw, state=m.Delivery.PREPARATION
    )
    if dv_model:
        dv_model = m.Delivery.objects.get(id=dv_model)
        new_dv.description = dv_model.description
        new_dv.producer_id = dv_model.producer_id
        new_dv.save()
        for pd in dv_model.product_set.all():
            pd.pk = None
            pd.delivery_id = new_dv.id
            pd.save()  # Will duplicate because pk==None

    if not m.NetworkMembership.objects.filter(network_id=nw.id, user_id=request.user.id, valid_until=None).exists():
        # I'm not staff, I must at least be producer of this network.
        # And the created delivery will be mine.
        if nw.producers.filter(id=request.user.id).exists():
            new_dv.producer_id = request.user.id
            new_dv.save()
        else:
            return HttpResponseForbidden("Must be admin or producer of this network")

    m.JournalEntry.log(
        request.user,
        "Created new delivery dv-%d %s in nw-%d %s",
        new_dv.id,
        name,
        nw.id,
        nw.name,
    )
    return redirect(
        reverse("edit_delivery_products", kwargs={"delivery": new_dv.id}) + "?new=true"
    )

def set_delivery_state(request, delivery, state):
    dv = get_delivery(delivery)
    if not request.user.is_staff and not m.NetworkMembership.objects.filter(
        user=request.user, network=dv.network, is_staff=True, valid_until=None
    ).exists():
        return HttpResponseForbidden(
            "Réservé aux administrateurs du réseau " + dv.network.name
        )
    if state not in m.Delivery.STATE_CHOICES:
        return HttpResponseBadRequest(state + " n'est pas un état valide.")
    dv.state = state
    if state >= m.Delivery.FROZEN and dv.freeze_date is None:
        dv.freeze_date = m.Now()
    dv.save()
    m.JournalEntry.log(request.user, "Set state=%s in dv-%d", state, dv.id)

    target = request.GET.get("next")
    return redirect(target) if target else HttpResponse("")


    return _set_delivery_field(request, delivery, 'state', state)

def _set_network_field(request, network, name, val):
    """Change a delivery's state."""
    nw = get_network(network)
    if not m.NetworkMembership.objects.filter(
        user=request.user, network=network, is_staff=True, valid_until=None
    ).exists():
        return HttpResponseForbidden(
            "Réservé aux administrateurs du réseau " + network.name
        )

    setattr(nw, name, val)
    nw.save()
    m.JournalEntry.log(
        request.user,
        "Set %s=%s in nw-%d",
        name, val, nw.id)

    target = request.GET.get("next")
    return redirect(target) if target else HttpResponse("")

def set_network_visibility(request, network, val):
    b = val.lower() in ('on', 'true', '1')
    return _set_network_field(request, network, 'visible', b)

def set_network_validation(request, network, val):
    b = val.lower() in ('on', 'true', '1')
    return _set_network_field(request, network, 'auto_validate', b)

@nw_admin_required(lambda a: get_delivery(a["delivery"]).network)
def set_delivery_name(request, delivery, name):
    """Change a delivery's name."""
    dv = get_delivery(delivery)
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


def save_delivery(dv):
    """Save an Excel spreadsheet and a PDF table of a delivery that's just been completed."""
    file_name_xlsx = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.xlsx" % dv.id)
    with open(file_name_xlsx, "wb") as f:
        f.write(spreadsheet(dv, [dv.network]))
    # file_name_pdf = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.pdf" % dv.id)
    # with open(file_name_pdf, 'wb') as f:
    #     f.write(latex_delivery_table(dv))


@nw_admin_required()
def view_emails_pdf(request, network):
    nw = get_network(network)
    return latex.emails(nw)


@login_required()
def view_emails(request, network):
    user = request.user
    vars = {"user": user}
    nw = get_network(network)
    vars["network"] = nw
    if user not in nw.staff.all():
        return HttpResponseForbidden("Réservé aux admins")
    return render(request, "emails.html", vars)


@login_required()
def view_directory(request, network):
    user = request.user
    nw = get_network(network)
    members = {
        "Administrateurs": [],
        "Producteurs": [],
        "Régulateurs": [],
        "Acheteurs": [],
        "Candidats": []
    }
    vars = {"user": user, "nw": nw, "members": members} 
    if not user.is_staff and not m.NetworkMembership.objects.filter(network_id=nw.id, user_id=user.id, valid_until=None, is_staff=True).exists():
        return HttpResponseForbidden("Réservé aux admins")
    for mb in (m.NetworkMembership.objects
        .filter(network_id=nw, valid_until=None)
        .select_related("user")
        .select_related("user__florealuser")):
        if mb.is_staff:
            cat = 'Administrateurs'
        elif mb.is_producer:
            cat = 'Producteurs'
        elif mb.is_regulator:
            cat = 'Régulateurs'
        elif mb.is_buyer:
            cat = 'Acheteurs'
        elif mb.is_candidate:
            cat = 'Candidats'
        else:
            continue
        members[cat].append(mb.user)
    return render(request, "directory.html", vars)


@login_required()
def view_history(request):
    # Deliveries in which the current user has purchased something
    # TODO: make it a single request for purchases, then group them by delivery,
    # either here in a single pass or in the template with:
    #
    #     {% regroup purchases by delivery as purchases_by_delivery %}
    #     {% for dv_pc in purchases_by_delivery %}
    #     {% with dv=dv_pc.grouper %}
    #     {% for pc in dv_pc.list %}
    deliveries = [
        {
            "delivery": dv,
            "network": dv.network,
            "purchases": m.Purchase.objects.filter(
                product__delivery=dv, user=request.user
            ),
        }
        for dv in m.Delivery.objects.filter(product__purchase__user=request.user).distinct()
    ]
    for x in deliveries:
        x["price"] = sum(y.price for y in x["purchases"])
    vars = {"user": request.user, "deliveries": deliveries}
    return render(request, "view_history.html", vars)


JOURNAL_LINKS = {
    "cd": "/admin/floreal/candidacy/%d/",
    "nw": "/nw-%d",
    "u": "/admin/auth/user/%d/",
    "dv": "/dv-%d/staff",
}


@nw_admin_required()
def journal(request):
    journal_link_re = re.compile(r"\b([a-z][a-z]?)-([0-9]+)")

    def add_link_to_actions(m):
        txt, code, n = m.group(0, 1, 2)
        href = JOURNAL_LINKS.get(code)
        return "<a href='%s'>%s</a>" % (href % int(n), txt) if href else txt

    days = []
    current_day = None
    n = request.GET.get('n', 1024)
    for entry in m.JournalEntry.objects.all().select_related("user").order_by("-date")[:n]:
        today = entry.date.strftime("%x")
        action = journal_link_re.sub(add_link_to_actions, html.escape(entry.action))
        record = {
            "user": entry.user,
            "hour": entry.date.strftime("%XZ"),
            "action": action,
        }
        if not current_day or current_day["day"] != today:
            current_day = {"day": today, "entries": [record]}
            days.append(current_day)
        else:
            current_day["entries"].append(record)
    return render(request, "journal.html", {"user": request.user, "days": days})


def editor(
    request, target=None, title="Éditer", template="editor.html", content=None, **kwargs
):
    ctx = dict(
        title=title, target=target or request.path, content=content or "", 
        next=request.GET.get('next'), **kwargs
    )
    ctx.update(csrf(request))
    return render(request, template, ctx)


@nw_admin_required()
def set_message(request):
    if request.method == "POST":
        P = request.POST
        d = P["destination"].split("-")
        # TODO: check that user has the admin rights suitable for the destination
        if d[0] == "everyone":
            network_id = None
        elif d[0] == "nw":
            network_id = int(d[1])
        else:
            assert False
        text = P["editor"]
        if text.startswith("<p>"):
            text = text[3:]
            if text.endswith("</p>"):
                text = text[:-4]
        msg = m.AdminMessage.objects.create(message=text, network_id=network_id)
        m.JournalEntry.log(request.user, "Posted a message to %s", f"nw-{network_id}" if network_id else "everyone")
        target = request.GET.get("next", "index")
        return redirect(target)
    else:
        u = request.user
        if u.is_staff:
            options = [("Tout le monde", "everyone")] + [
            ("Réseau %s" % nw.name, "nw-%d" % nw.id) for nw in m.m.Network.objects.all()]
        else:
            options = [
                ("Réseau %s" % nw.name, "nw-%d" % nw.id) 
                for nw in m.Network.objects.filter(
                    networkmembership__user_id=u.id,
                    networkmembership__is_staff=True,
                    networkmembership__valid_until=None
                )] 
        return editor(
            request,
            title="Message administrateur",
            template="set_message.html",
            target="/set-message",
            options=options,
        )


@nw_admin_required()
def unset_message(request, id):
    # TODO check that user is allowed for that message
    # To be done in a m.Message method
    m.AdminMessage.objects.get(id=int(id)).delete()
    target = request.GET.get("next", "index")
    return redirect(target)

# Used to decode short Google "plus codes"
CENTRAL_LATITUDE = 43.5
CENTRAL_LONGITUDE = 1.5
POSITION_REGEXP = re.compile(r"([+-]?\d+(?:\.\d*)?),([+-]?\d+(?:\.\d*)?)")

def _description_and_image(request, obj, title):
    if request.method == "POST":
        obj.description = request.POST["editor"]
        img = request.FILES.get('image')
        if img:
            obj.image_description = img

        if (pos := request.POST.get('position')):
            try:
                (obj.latitude, obj.longitude) = plus_code.to_lat_lon(pos)
            except ValueError:
                if (match := POSITION_REGEXP.match(pos.replace(' ', ''))):
                    (obj.latitude, obj.longitude) = (float(x) for x in match.groups())
                else:
                    return HttpResponseBadRequest("Position invalide")

        if (sdescr := request.POST.get('short_description')) is not None:
            obj.short_description = sdescr

        obj.save()

        return redirect(request.GET.get('next', 'admin'))
    else:
        return editor(
            request, title=title,
            template='description_and_image.html',
            content=obj.description,
            obj=obj,
            has_short_description=hasattr(obj, "short_description")
        )

@nw_admin_required()
def network_description_and_image(request, network):
    nw = get_network(network)
    return _description_and_image(request, nw, f"Présentation du réseau {nw.name}")

@nw_admin_required()
def user_description_and_image(request, user):
    flu = m.FlorealUser.objects.get(user_id=user)
    return _description_and_image(request, flu, f"Présentation de {flu.user.first_name} {flu.user.last_name}")


def map(request):
    networks = m.Network.objects.filter(visible=True, latitude__isnull=False)
    if not request.user.is_anonymous:
        networks = [*networks, *m.Network.objects.filter(visible=False, networkmembership__user=request.user, latitude__isnull=False).distinct()]
    producers = m.FlorealUser.objects.filter(
        user__networkmembership__network__in=networks,
        user__networkmembership__is_producer=True,
        latitude__isnull=False,
    ).distinct().select_related('user')
    return render(request, "map.html", {
        "user": request.user, 
        'networks': networks,
        'producers': producers,    
    })
