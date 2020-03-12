#!/usr/bin/python
# -*- coding: utf-8 -*-

import os

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required

from caracole import settings
from .decorators import nw_admin_required
from .getters import get_delivery, get_subgroup
from . import latex
from .spreadsheet import spreadsheet
from .delivery_description import delivery_description


MIME_TYPE = {
    'pdf': "application/pdf",
    'xlsx': "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def non_html_response(name_bits, name_extension, content):
    """Common helper to serve PDF and Excel content."""
    filename = ("_".join(name_bits) + "." + name_extension).replace(" ", "_")
    mime_type = MIME_TYPE[name_extension]
    response = HttpResponse(content_type=mime_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(content)
    return response


@login_required()
def view_purchases_html(request, delivery, subgroup=None):
    """View purchases for a given delivery, possibly restricted to a subgroup. (subgroup) staff only."""
    dv = get_delivery(delivery)
    if subgroup:
        sg = get_subgroup(subgroup)
        if request.user not in sg.staff.all() and request.user not in sg.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        subgroups = [sg]
    else:
        if request.user not in dv.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        subgroups = dv.network.subgroup_set.all()
    return render_to_response('view_purchases.html', delivery_description(dv, subgroups))


@login_required()
def view_purchases_xlsx(request, delivery, subgroup=None):
    """View purchases for a given delivery as an MS-Excel spreadsheet, possibly restricted to a subgroup.
    (subgroup) staff only."""
    dv = get_delivery(delivery)
    if subgroup:
        sg = get_subgroup(subgroup)
        if request.user not in sg.staff.all() and request.user not in sg.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        subgroups = [sg]
    else:
        if request.user not in dv.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        subgroups = dv.network.subgroup_set.all()
    return non_html_response((dv.network.name, dv.name), "xlsx", spreadsheet(dv, subgroups))


@login_required()
def view_purchases_latex(request, delivery, subgroup=None):
    """View purchases for a given delivery as a PDF table, generated through LaTeX, possibly restricted to a subgroup.
    (subgroup) staff only."""
    dv = get_delivery(delivery)
    if subgroup:
        sg = get_subgroup(subgroup)
        if request.user not in sg.staff.all() and request.user not in sg.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        content = latex.subgroup(dv, sg)
        name_bits = (dv.network.name, dv.name, sg.name)
    else:
        if request.user not in dv.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        content = latex.delivery_table(dv)
        name_bits = (dv.network.name, dv.name)
    return non_html_response(name_bits, "pdf", content)


@login_required()
def view_cards_latex(request, delivery, subgroup=None):
    """View purchases for a given delivery as a PDF table, generated through LaTeX, possibly restricted to a subgroup.
    Subgroups are presented as ready-to-cut tables, whole deliveries as list per subgroup. (subgroup) staff only."""
    dv = get_delivery(delivery)
    if subgroup:
        sg = get_subgroup(subgroup)
        if request.user not in sg.staff.all() and request.user not in sg.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        content = latex.cards(dv, sg)
        name_bits = (dv.network.name, dv.name, sg.name)
    else:
        content = latex.delivery_cards(dv)
        name_bits = (dv.network.name, dv.name)
    return non_html_response(name_bits, "pdf", content)


@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def get_archive(request, delivery, suffix):
    """Retrieve the PDF/MS-Excel file versions of a terminated delivery which have been saved upontermination."""
    dv = get_delivery(delivery)
    file_name = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.%s" % (dv.id, suffix))
    with open(file_name) as f:
        content = f.read()
    name_bits = (dv.network.name, dv.name)
    return non_html_response(name_bits, suffix, content)