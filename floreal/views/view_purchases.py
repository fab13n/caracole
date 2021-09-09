#!/usr/bin/python3

import os
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import json
from typing import List, Tuple, Dict, Set

from django.conf import settings
from .decorators import nw_admin_required
from .getters import get_delivery, get_network, get_subgroup
from . import latex
from .spreadsheet import spreadsheet
from .delivery_description import FlatDeliveryDescription, GroupedDeliveryDescription, UserDeliveryDescription
from .. import models as m
from .latex import render_latex


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
        Q(is_staff=True) | Q(is_producer=True),
        user=request.user, network=dv.network, valid_until=None
    ).exists():
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
    #if not isinstance(dd, UserDeliveryDescription) and not (dd.rows and dd.products):
    #    return HttpResponse("Aucun achat dans cette commande", status=404)
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


def all_deliveries(request, network, states):

    if request.user.is_staff:
        pass # Global admin
    elif m.NetworkMembership.objects.filter(
        is_staff=True,
        user=request.user,
        valid_until=None,
        network_id=int(network)
    ).exists():
        pass  # Admin for this network
    else:
        raise ValueError("Accès interdit")

    nw = get_network(network)

    purchases = (m.Purchase.objects.filter(
            product__delivery__state__in=states, 
            product__delivery__network=nw)
            .select_related('user', 'product__delivery')
            .distinct()
    )

    all_deliveries = m.Delivery.objects.filter(network=nw, state__in=states)

    # User -> set of devliveries where he ordered
    d: Dict[m.User, Set[m.Delivery]] = {}

    for pc in purchases:
        dv = pc.product.delivery
        if (deliveries := d.get(pc.user)) is None:
            deliveries = d[pc.user] = {dv}
        else:
            deliveries.add(dv)
 
    t: List[Tuple[m.User, List[Tuple[m.Delivery, bool]]]] = [
        (u, [(dv, dv in with_purchases) for dv in all_deliveries])
        for u, with_purchases in d.items()
    ]
    t.sort(key=lambda x: (x[0].last_name.lower(), x[0].first_name.lower()))

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
