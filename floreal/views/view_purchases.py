#!/usr/bin/python3

import os
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json
from typing import List, Tuple

from django.conf import settings
from .decorators import nw_admin_required
from .getters import get_delivery, get_network, get_subgroup
from . import latex
from .spreadsheet import spreadsheet
from .delivery_description import FlatDeliveryDescription, GroupedDeliveryDescription, UserDeliveryDescription
from .. import models as m

MIME_TYPE = {
    'json': "text/json", # TODO check correct name
    'pdf': "application/pdf",
    'xlsx': "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def non_html_response(name_stem, name_extension, content):
    """Common helper to serve PDF and Excel content."""
    mime_type = MIME_TYPE[name_extension]
    response = HttpResponse(content_type=mime_type)
    if name_stem is not None:
        filename = (name_stem + "." + name_extension).replace(" ", "_")
        response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(content)
    return response


def render_description(request, delivery, renderer, extension, subgroup=None, user: bool=False, download=True):
    """
    Retrieve the delivery description associated with those url params if permissions allow.
    """
    dv = get_delivery(delivery)
    # Permission
    if not user and not request.user.is_staff and not m.NetworkMembership.objects.filter(
        user=user, network=dv.network, is_staff=True, valid_until=None
    ).exists():
        # TODO authorize producers
        return HttpResponseForbidden(f"Pas autorisé pour {dv.network.name}")

    if user:
        dd = UserDeliveryDescription(dv, request.user, empty_products=True)
    elif subgroup is not None:
        sg = get_subgroup(subgroup)
        dd = FlatDeliveryDescription(dv, subgroup=sg)
    elif dv.network.grouped:
        dd = GroupedDeliveryDescription(dv)
    else:
        dd = FlatDeliveryDescription(dv)

    name_stem = dd.delivery.name if download else None
    if not isinstance(dd, UserDeliveryDescription) and not (dd.rows and dd.products):
        return HttpResponse("Aucun achat dans cette livraison", status=404)
    return non_html_response(name_stem, extension, renderer(dd))


def view_purchases_html(request, delivery, subgroup=None):
    """
    View purchases for a given delivery, possibly restricted to a subgroup. (subgroup) staff only.
    HTML template isn't loading the delivery content directly, it requests data through AJAX.
    """
    return render(request,'view_purchases.html', {
        'user': request.user,
        'subgroup': get_subgroup(subgroup) if subgroup is not None else None,
        'delivery': get_delivery(delivery)
    })


def view_purchases_xlsx(request, delivery, subgroup=None):
    """View purchases for a given delivery as an MS-Excel spreadsheet, possibly restricted to a subgroup.
    (subgroup) staff only."""
    m.JournalEntry.log(request.user, "Downloaded Excel purchases for dv-%s", delivery)
    return render_description(
        request=request, delivery=delivery,
        renderer=spreadsheet, extension='xlsx'
    )


def view_purchases_latex_table(request, delivery, subgroup=None):
    """View purchases for a given delivery as a PDF table, possibly restricted to a subgroup.
    (subgroup) staff only."""
    m.JournalEntry.log(request.user, "Downloaded PDF purchases for dv-%s", delivery)
    return render_description(
        request=request, delivery=delivery,
        renderer=latex.table, extension='pdf'
    )

def view_purchases_latex_cards(request, delivery, subgroup=None):
    """View purchases for a given delivery as an MS-Excel spreadsheet, possibly restricted to a subgroup.
    (subgroup) staff only."""
    m.JournalEntry.log(request.user, "Downloaded PDF purchases (cards) for dv-%s", delivery)
    return render_description(
        request=request, delivery=delivery,
        renderer=latex.cards, extension='pdf'
    )


def view_purchases_json(request, delivery, subgroup=None, user: bool = False):
    return render_description(
        download=False,
        request=request, delivery=delivery, user=user,
        renderer=lambda dd: json.dumps(dd.to_json()), extension='json'
    )


@nw_admin_required()
def all_deliveries(request, network, states):
    nw = get_network(network)

    if False:
        # TODO the whole thing could be done in a single query as follows,
        # with the main issue being that only the user and delivery ids,
        # not actual objects, are extracted by .values().
        q = (m.Purchase.objects.filter(
                product__delivery__state__in=states, 
                product__delivery__network=nw)
                .values('user', 'product__delivery')
                .distinct()
        )
        # This allows to get back full objects quickly, but that's still ugly
        deliveries = m.Delivery.objects.filter(id__in=[x['product_delivery'] for x in q])
        users = m.User.objects.filter(id__in=[x['user'] for x in q])
    

    deliveries = list(m.Delivery.objects.filter(network=nw, state__in=states))
    users = m.User.objects.filter(member_of_network=nw, is_active=True)

    # u_id -> dv -> has_purchased
    users_with_purchases = {u: {dv: False for dv in deliveries} for u in users}

    for dv in deliveries:
        # TODO here's the nasty query-in-a-loop
        for u in users.filter(purchase__product__delivery=dv).distinct():
            users_with_purchases[u][dv] = True

    # Remove users with no purchases in any selected delivery
    users_with_purchases = {
        u: dv_pc
        for u, dv_pc in users_with_purchases.items()
        if any(v for v in dv_pc.values())
    }
            
    t: List[Tuple[m.User, List[Tuple[m.Delivery, bool]]]] = [
            (u, [(dv, dv_pc[dv]) 
            for dv in deliveries]) 
            for u, dv_pc in users_with_purchases.items()
    ]
    t.sort(key=lambda x: (x[0].last_name, x[0].first_name))

    return {'states': states, 'network': nw, 'table': t}


def all_deliveries_html(request, network, states):
    ctx = all_deliveries(request, network, states)
    return render(request,"all_deliveries.html", ctx)


def all_deliveries_latex(request, network, states):
    ctx = all_deliveries(request, network, states)
    content = render_latex("all_deliveries.tex", ctx)
    return non_html_response(get_network(network).name, "pdf", content)


@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def get_archive(request, delivery, suffix):
    """Retrieve the PDF/MS-Excel file versions of a terminated delivery which have been saved upontermination."""
    dv = get_delivery(delivery)
    file_name = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.%s" % (dv.id, suffix))
    with open(file_name, 'rb') as f:
        content = f.read()
    name_bits = (dv.network.name, dv.name)
    return non_html_response(name_bits, suffix, content)
