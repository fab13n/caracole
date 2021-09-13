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
from django.db.models.functions import Lower
from openlocationcode import openlocationcode
import pytz

from villes import plus_code
from pages.models import TexteDAccueil

from .. import models as m
from .getters import get_network, get_delivery, must_be_prod_or_staff, must_be_staff

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
    all_deliveries_html,
    all_deliveries_latex,
)
from .spreadsheet import spreadsheet
from .candidacies import (
    cancel_candidacy,
    validate_candidacy,
    leave_network,
    create_candidacy,
    manage_candidacies,
)
from .invoice_mail import invoice_mail_form
from .users import users_json, users_html
from . import delivery_description as dd
from . import latex


def index(request):
    try:
        accueil = TexteDAccueil.objects.all().first().texte_accueil
    except AttributeError:
        accueil = "Penser à renseigner le texte d'accueil :-)"
    if request.user.is_anonymous:
        vars = {"networks": m.Network.objects.exclude(visible=False).exclude(active=False), "accueil": accueil}
        vars.update(csrf(request))
        return render(request, "index_unlogged.html", vars)
    else:
        mbships = list(m.NetworkMembership.objects
            .filter(user=request.user, valid_until=None, network__active=True)
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
            "unsubscribed": m.Network.objects \
                .exclude(members=request.user) \
                .exclude(visible=False) \
                .exclude(active=False)
        }
        return render(request, "index_logged.html", vars)


from collections import defaultdict

def admin(request):
    if request.user.is_anonymous:
        return HttpResponseForbidden("Réservé aux administrateurs et producteurs")
    if (only := request.GET.get('only')):
        networks = m.Network.objects.filter(
            id=only,
            networkmembership__user=request.user,
            networkmembership__is_staff=True,
            networkmembership__valid_until=None,
        )
        messages = m.AdminMessage.objects.filter(network_id=only)
        is_network_staff = {int(only): True}
    elif request.user.is_staff:
        # Global staff
        networks = m.Network.objects.filter(active=True)
        messages = m.AdminMessage.objects.all()
        is_network_staff = defaultdict(lambda: True)
    else:
        # Only staff / prod of some networks
        staff_networks = (m.Network.objects
            .filter(networkmembership__is_staff=True,
                    active=True,
                    networkmembership__user=request.user,
                    networkmembership__valid_until=None)
        )
        prod_networks = (m.Network.objects
            .filter(networkmembership__is_producer=True,
                    active=True,
                    networkmembership__user=request.user,
                    networkmembership__valid_until=None)
        )
        networks = staff_networks | prod_networks
        messages = m.AdminMessage.objects.filter(network__in=networks)
        is_network_staff = defaultdict(lambda: False)
        for nw in staff_networks:
            is_network_staff[nw.id] = True

    deliveries = (m.Delivery.objects
        .filter(network__in=networks, state__in="ABCD")
        .select_related("producer")
    ).order_by(
        "state",
        "distribution_date",
        "freeze_date",
        "id"
    )
    candidacies = (m.NetworkMembership.objects
        .filter(network__in=networks,
                is_candidate=True,
                valid_until=None)
        .select_related("user")
    )
    deliveries_without_purchase = {dv.id for dv in m.Delivery.objects
        .exclude(state='E')
        .exclude(product__purchase__isnull=False)
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
            "is_network_staff": is_network_staff[nw.id],  # Otherwise producer
            "visible": nw.visible,
            "auto_validate": nw.auto_validate,
        }

    for cd in candidacies:
        jnetworks[cd.network_id]["candidates"].append(cd.user)

    for dv in deliveries:
        jnw = jnetworks[dv.network_id]
        if not jnw["is_network_staff"] and dv.producer_id != request.user.id:
            # Producers only see their deliveries
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
        "messages": messages,
        "networks": jnetworks.values(),
        "Delivery": m.Delivery,
    }
    
    return render(request, "admin_reseaux.html", context)

@login_required()
def orders(request):
    networks = m.Network.objects.filter(
        networkmembership__user=request.user,
        networkmembership__is_buyer=True,
        networkmembership__valid_until=None,
        active=True,
    )
    deliveries = m.Delivery.objects.filter(
        network__in=networks,
        state__in="BCD",
    )
    purchases = m.Purchase.objects.filter(
        product__delivery__in=deliveries,
        user=request.user,
    ).select_related("product")

    messages = m.AdminMessage.objects.filter(
        network__in=networks
    ).order_by("id")

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
        and m.Delivery.objects.filter(state=m.Delivery.ORDERING_ALL, network=nw).exists(),
        "user_status": status,
    }
    return render(request, "reseau.html", vars)

def _dv_has_no_purchase(dv):
    # for pd in dv.product_set.all():
    #     if pd.purchase_set.exists():
    #         return False
    # return True
    return not m.Purchase.objects.filter(
        product__delivery=dv,
    ).exists()


def archived_deliveries(request, network):
    must_be_prod_or_staff(request, network)
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


def delete_archived_delivery(request, delivery):
    dv = get_delivery(delivery)
    must_be_prod_or_staff(request, dv.network)
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


def delete_all_archived_deliveries(request, network):
    nw = get_network(network)
    must_be_prod_or_staff(request, nw)
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


def list_delivery_models(request, network, all_networks=False):
    """Propose to create a delivery based on a previous delivery.
    Can draw models from a signle network, or from eveyr network one's
    staff or producer of.
    """
    nw = m.Network.objects.get(id=network)
    if all_networks:
        authorized_networks = m.Network.objects.filter(
            networkmembership__is_staff=True,
            networkmembership__user=request.user, 
            networkmembership__valid_until=None)
        deliveries = m.Delivery.objects.filter(network__in=authorized_networks).select_related("network")
        is_producer = False
    else:
        which = must_be_prod_or_staff(request, nw)
        deliveries = m.Delivery.objects.filter(network=nw)
        if which == "producer":
            deliveries = deliveries.filter(producer_id=request.user.id)

    # Remove deliveries without products nor description
    deliveries = (deliveries 
        .filter(Q(product__isnull=False)|Q(description__isnull=False))
        .distinct()
    )

    vars = {
        "user": request.user,
        "nw": nw,
        "all_networks": all_networks,
        "producer": request.user if is_producer else None,
        "deliveries": deliveries.order_by("network", "-id"),
    }
    return render(request, "list_delivery_models.html", vars)


def create_delivery(request, network, dv_model=None):

    if dv_model:
        dv_model = m.Delivery.objects.get(id=dv_model)
    else:
        dv_model = None

    """Create a new delivery, then redirect to its edition page."""
    nw = get_network(network)
    which = must_be_prod_or_staff(request, nw)
    if which == "producer" and dv_model.producer_id != request.user.id:
        return HttpResponseForbidden("Les producteurs ne peuvent cloner que leurs propres commandes")

    if dv_model is not None:
        new_dv = m.Delivery.objects.create(
            name=dv_model.name, 
            network=nw, 
            state=m.Delivery.PREPARATION,
            producer_id=dv_model.producer_id,
            description=dv_model.description,
        )
        for pd in dv_model.product_set.all():
            pd.pk = None
            pd.delivery_id = new_dv.id
            pd.save()  # Will duplicate because pk==None
    else:
        # Come up with a name, set producer if producer-created, and that's it
        now = datetime.now()
        months = 'Janvier Février Mars Avril Mai Juin Juillet Août Septembre Octobre Novembre Décembre'.split()

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
        )

    m.JournalEntry.log(
        request.user,
        "Created new delivery dv-%d %s in nw-%d %s",
        new_dv.id,
        new_dv.name,
        nw.id,
        nw.name,
    )
    return redirect(
        reverse("edit_delivery_products", kwargs={"delivery": new_dv.id})
    )


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


    return _set_delivery_field(request, delivery, 'state', state)


def _set_network_field(request, network, name, val):
    """Change a delivery's state."""
    nw = get_network(network)
    must_be_prod_or_staff(request, nw)
    
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

def set_delivery_name(request, delivery, name):
    """Change a delivery's name."""
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


def view_emails_pdf(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    return latex.emails(nw)


def view_emails(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    user = request.user
    vars = {"user": user, "network": nw}
    return render(request, "emails.html", vars)


def view_directory(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    user = request.user
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
        .select_related("user__florealuser")
        .order_by(Lower("user__last_name"), Lower("user__first_name"))):
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

    purchases = m.Purchase.objects.filter(
        user=request.user
    ).select_related('user', 'product', 'product__delivery', 'product__delivery__network')

    total = 0
    networks = {}  # {nw_name -> {total: float, deliveries: {dv_name -> {total: int, purchases: [purchase+]}}}}

    for pc in purchases:
        dv = pc.product.delivery
        if dv.distribution_date is not None:
            dv_name = str(dv.distribution_date) + '|' + dv.name
        else:
            dv_name = dv.name
        nw_name = pc.product.delivery.network.name
        if (nw := networks.get(nw_name)) is None:
            networks[nw_name] = nw = {'total': 0, 'deliveries': {}}
        if (dv := nw['deliveries'].get(dv_name)) is None:
            nw['deliveries'][dv_name] = dv = {'total': 0, 'purchases': []}
        p = pc.price
        nw['total'] += p
        dv['total'] += p
        total += p
        dv['purchases'].append(pc)
    vars = {"user": request.user, "networks": networks, "total": total}
    return render(request, "view_history.html", vars)


JOURNAL_LINKS = {
    "cd": "/admin/floreal/candidacy/%d/",
    "nw": "/admin/reseaux.html#nw-%d",
    "u": "/admin/users.html?selected=%d",
    "dv": "/admin/dv-%d/edit",
}


def journal(request):
    must_be_staff(request)
    journal_link_re = re.compile(r"\b([a-z][a-z]?)-([0-9]+)")

    def add_link_to_actions(m):
        txt, code, n = m.group(0, 1, 2)
        href = JOURNAL_LINKS.get(code)
        return "<a href='%s'>%s</a>" % (href % int(n), txt) if href else txt

    days = []
    current_day = None
    n = request.GET.get('n', 1024)
    tz = pytz.timezone(settings.TIME_ZONE)
    for entry in m.JournalEntry.objects.all().select_related("user").order_by("-date")[:n]:
        date = entry.date.astimezone(tz)
        today = date.strftime("%x")
        action = journal_link_re.sub(add_link_to_actions, html.escape(entry.action))
        record = {
            "user": entry.user,
            "hour": date.strftime("%X"),
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


def set_message(request, id=None):
    if id is not None:
        msg = m.AdminMessage.objects.get(pk=id)
        must_be_prod_or_staff(request, msg.network_id)
    else:
        msg = None

    if request.method == "POST":
        P = request.POST
        d = P["destination"].split("-")
        if d[0] == "everyone":
            network_id = None
        elif d[0] == "nw":
            network_id = int(d[1])
        else:
            assert False

        must_be_prod_or_staff(request, network_id)
        
        text = P["editor"]
        if text.startswith("<p>"):
            text = text[3:]
            if text.endswith("</p>"):
                text = text[:-4]
        if msg is not None:
            msg.message = text
            msg.network_id = network_id
            msg.save()
            m.JournalEntry.log(request.user, "Modified message msg-%i to %s", msg.id, f"nw-{network_id}" if network_id else "everyone")
        else:
            msg = m.AdminMessage.objects.create(message=text, network_id=network_id)
            m.JournalEntry.log(request.user, "Posted message msg-%i to %s", msg.id, f"nw-{network_id}" if network_id else "everyone")
        target = request.GET.get("next", "index")
        return redirect(target)
    else:
        u = request.user
        if u.is_staff:
            options = [("Tout le monde", "everyone")] + [
            ("Réseau %s" % nw.name, f"nw-{nw.id}") for nw in m.Network.objects.all()]
        else:
            options = [
                ("Réseau %s" % nw.name, f"nw-{nw.id}") 
                for nw in m.Network.objects.filter(
                    Q(networkmembership__is_staff=True) | Q(networkmembership__is_producer=True),
                    networkmembership__user_id=u.id,
                    networkmembership__valid_until=None
                )]
        if msg is None:
            selected_option = options[0][0]
        elif msg.network_id is None:
            selected_option = "everyone"
        else:
            selected_option = f"nw-{msg.network_id}"
        return editor(
            request,
            title="Message administrateur",
            template="set_message.html",
            target=f"/set-message/{id}" if msg is not None else "/set-message",
            options=options,
            content=msg.message if msg is not None else "",
            selected_option=selected_option
        )


def unset_message(request, id):
    # TODO check that user is allowed for that message
    # To be done in a m.Message method
    msg = m.AdminMessage.objects.get(id=int(id))
    must_be_prod_or_staff(request, msg.network)
    m.JournalEntry.log(request.user, "Deleted message %i to %s", msg.id, f"nw-{msg.network_id}" if msg.network_id else "everyone")
    msg.delete()
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


def network_description_and_image(request, network):
    nw = get_network(network)
    must_be_staff(request, nw)
    return _description_and_image(request, nw, f"Présentation du réseau {nw.name}")


def user_description_and_image(request, user):
    flu = m.FlorealUser.objects.get(user_id=user)
    if request.user.is_staff:
        pass  # global admins can edit everyone
    elif flu.user == request.user:
        pass  # one can always edit oneself
        # TODO: but there's no link pointing there yet.
        # Add the option to producers in admin page.
    elif m.NetworkMembership.objects.filter(
        valid_until=None,     # Edited user...
        user=flu.user,        # ...is currently...
        is_producer=True,     # ...a producer in a network...
        network__networkmembership__user=request.user,  # ...where the requester...
        network__networkmembership__valid_until=None,   # ...is currently...
        network__networkmembership__is_staff=True,      # ...an administrator
    ).exists():
        pass  # request.user administrates a network in which flu is a producer
    else:
        return HttpResponseForbidden("Vous n'avez pas le droit d'éditer cette fiche")

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
