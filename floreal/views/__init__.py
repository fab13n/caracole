#!/usr/bin/python3

from datetime import datetime
import os
import re
from collections import defaultdict

from django.shortcuts import render, redirect, reverse
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import html
from django.template.context_processors import csrf
from django.db.models import Count, Q

from caracole import settings
from .. import models as m
from .getters import get_network, get_delivery
from .decorators import nw_admin_required, regulator_required

from .edit_delivery_purchases import edit_delivery_purchases
from .edit_user_purchases import edit_user_purchases
from .user_registration import user_register, user_register_post
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

from floreal.views import require_phone_number as phone


def index(request):
    if request.user.is_anonymous:
        my_networks = list()
        vars = {"networks": m.Network.objects.exclude(visible=False)}
        vars.update(csrf(request))
        return render(request, "index_unlogged.html", vars)
    else:
        mbships = list(m.NetworkMembership.objects.filter(user=request.user))
        for nm in mbships:
            hoo = (
                nm.is_buyer
                and m.Delivery.objects.filter(
                    network=nm.network, state=m.Delivery.ORDERING_ALL
                ).exists()
            )
            nm.has_open_orders = hoo

        vars = {
            "user": request.user,
            "memberships": mbships,
            "unsubscribed": m.Network.objects.exclude(members=request.user).exclude(
                visible=False
            ),
        }
        return render(request, "index_logged.html", vars)


@login_required()
def admin(request):
    vars = {
        "messages": m.AdminMessage.objects.all(),  # TODO only those I administrate
        "user": request.user,
        "memberships": m.NetworkMembership.objects.filter(user=request.user),
    }
    return render(request, "admin_circuits.html", vars)


@login_required()
def orders(request):
    networks = [
        mb.network
        for mb in m.NetworkMembership.objects.filter(
            user=request.user, is_buyer=True
        ).only("network")
    ]
    networks_and_deliveries = []
    for nw in networks:
        open_deliveries = list(
            m.Delivery.objects.filter(state=m.Delivery.ORDERING_ALL, network=nw)
        )
        if open_deliveries:
            networks_and_deliveries.append(
                (
                    nw,
                    [
                        dd.UserDeliveryDescription(dv, request.user).to_json()
                        for dv in open_deliveries
                    ],
                )
            )

    vars = {
        "user": request.user,
        "networks_and_deliveries": networks_and_deliveries
    }
    return render(request, "orders.html", vars)


@login_required()
def order(request):
    vars = {}
    return render(request, "order.html", vars)


@login_required()
def user(request):
    vars = {}
    return render(request, "user.html", vars)


@login_required()
def circuit(request, network):
    nw = get_network(network)
    mb = m.NetworkMembership.objects.filter(user=request.user, network=nw).first()
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
    return render(request, "circuit.html", vars)


@login_required()
def xxx_index(request):
    """Main page: list deliveries open for ordering as a user, networks for which the user is full admin,
    and orders for which he has subgroup-admin actions to take."""

    user = request.user

    vars = {"user": user, "Delivery": m.Delivery}
    vars["has_phone"] = phone.has_number(request.user)

    # Deliveries which need to be displayed, and maybe ordered on.
    # TODO Include order here rather than through filters

    member_of_networks = user.member_of_network.all()

    active_deliveries = (
        m.Delivery.objects.filter(network__in=member_of_networks)
        .filter(
            Q(state=m.Delivery.ORDERING_ALL)
            | Q(
                state__in=[m.Delivery.ORDERING_ADMIN, m.Delivery.FROZEN],
                product__purchase__user=user,
            )
        )
        .distinct()
    )

    # Purchases by this user in an active delivery.
    # Gathered with a single SQL query, reorganized by network/delivery
    # in Python. TODO fetch_related: this request is performed for every
    # request of the landing page!
    purchases = m.Purchase.objects.filter(
        user=user, product__delivery__in=active_deliveries
    )

    # Reorganize deliveries and purchases: network -> deliveries -> purchases
    networks_by_id = {nw.id: nw for nw in member_of_networks}  # nw.id -> nw
    deliveries_by_id = {dv.id: dv for dv in active_deliveries}
    deliveries_by_network = defaultdict(list)  # nw.id -> [dv+]
    for dv in active_deliveries:
        deliveries_by_network[dv.network.id].append(dv)
    purchases_by_delivery = {dv.id: [] for dv in active_deliveries}  # dv.id -> [pc*]
    for pc in purchases:
        purchases_by_delivery[pc.product.delivery_id].append(pc)
    vars["user_deliveries"] = [
        {
            "nw": networks_by_id[nw_id],
            "deliveries": [
                {
                    "dv": deliveries_by_id[dv.id],
                    "purchases": purchases_by_delivery[dv.id],
                    "price": sum(pc.price for pc in purchases_by_delivery[dv.id]),
                }
                for dv in deliveries
            ],
        }
        for nw_id, deliveries in deliveries_by_network.items()
    ]

    # Every pending candidacy for which I'm network staff
    vars["candidacies"] = [
        (u, nw) for nw in user.staff_of_network.all() for u in nw.candidates.all()
    ]

    # Admin messages to display
    vars["messages"] = {
        ("Message général", msg.message, msg.id)
        for msg in m.AdminMessage.objects.filter(network=None)
    } | {
        (nw.name, msg.message, msg.id)
        for nw in member_of_networks
        for msg in nw.adminmessage_set.all()
    }

    import json

    print("\n\nvars:\n", vars)
    return render(request, "index.html", vars)


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
    return redirect("archived_deliveries", nw.id)


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
    return redirect("archived_deliveries", network)


def create_network(request, nw_name, sg_name):
    user = request.user
    if not user.is_staff:
        return HttpResponseForbidden("Creation de réseaux réservée au staff")
    if m.Network.objects.filter(name__iexact=nw_name).exists():
        return HttpResponseBadRequest("Il y a déjà un réseau nommé " + nw_name)
    nw = m.Network.objects.create(name=nw_name)
    nw.staff.add(user)
    nw.members.add(user)
    target = request.GET.get("next", False)
    m.JournalEntry.log(user, "Created network nw-%d: %s", nw.id, nw_name)
    return redirect(target) if target else redirect("network_admin", network=nw.id)


def edit_delivery_staff(request, delivery):
    """Edit a delivery as a full network admin: act upon its lifecycle, control which subgroups have been validated,
    change the products characteristics, change other users' orders."""
    dv = m.Delivery.objects.get(id=delivery)
    if not m.NetworkMembership.objects.filter(
        user=request.user, network=dv.network, is_staff=True
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
        authorized_networks = request.user.staff_of_network.all()
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

    if not nw.staff.filter(id=request.user.id).exists():
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
    """Change a delivery's state."""
    dv = get_delivery(delivery)
    if not m.NetworkMembership.objects.filter(
        user=request.user, network=dv.network, is_staff=True
    ).exists():
        return HttpResponseForbidden(
            "Réservé aux administrateurs du réseau " + dv.network.name
        )
    if state not in m.Delivery.STATE_CHOICES:
        return HttpResponseBadRequest(state + " n'est pas un état valide.")
    must_save = (
        dv.state < m.Delivery.TERMINATED == state
        and m.Purchase.objects.filter(product__delivery=dv).exists()
    )
    dv.state = state
    dv.save()
    if must_save:
        save_delivery(dv)
    m.JournalEntry.log(
        request.user,
        "Set delivery dv-%d in state %s",
        dv.id,
        m.Delivery.STATE_CHOICES[state],
    )

    target = request.GET.get("next", False)
    return redirect(target) if target else HttpResponse("")


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
def view_phones(request, network):
    user = request.user
    vars = {"user": user}
    nw = get_network(network)
    if user not in nw.staff.all():
        return HttpResponseForbidden("Réservé aux admins")
    vars["nw"] = nw
    vars["staff"] = nw.staff.order_by("last_name", "first_name")
    vars["regulators"] = nw.regulators.exclude(id__in={u.id for u in vars["staff"]})
    vars["members"] = nw.regulators.exclude(
        id__in={u.id for x in ["staff", "regulators"] for u in vars[x]}
    )
    vars["producers"] = nw.producers.all()
    return render(request, "phones.html", vars)


@login_required()
def view_history(request):
    # Deliveries in which the current user has purchased something
    deliveries = [
        {
            "delivery": dv,
            "network": dv.network,
            "purchases": m.Purchase.objects.filter(
                product__delivery=dv, user=request.user
            ),
        }
        for dv in m.Delivery.objects.filter(product__purchase__user__in=[request.user])
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
    for entry in m.JournalEntry.objects.all().order_by("-date")[:1024]:
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
        title=title, target=target or request.path, content=content or "", **kwargs
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
        return redirect("index")
    else:
        u = request.user
        options = [("Tout le monde", "everyone")] + [
            ("Réseau %s" % nw.name, "nw-%d" % nw.id) for nw in u.staff_of_network.all()
        ]
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
    return redirect("index")


@nw_admin_required()
def edit_network_description(request, network):
    nw = get_network(network)
    if request.method == "POST":
        nw.description = request.POST["editor"]
        nw.save()
        return redirect("network_admin", nw.id)
    else:
        return editor(
            request, title="Présentation du réseau " + nw.name, content=nw.description
        )