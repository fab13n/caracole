#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.http import HttpResponse
from django.shortcuts import render_to_response

from ..models import Delivery, Subgroup
from . import pdf
from .spreadsheet import spreadsheet
from .delivery_description import delivery_description


def get_subgroup(request, network):
    if 'subgroup' in request.GET:
        return Subgroup.objects.get(network=network, name__iexact=request.GET['subgroup'])
    else:
        return network.subgroup_set.get(staff__in=[request.user])

def _non_html_response(name_bits, name_extension, mime_type, content):
    """Common helper to serve PDF and Excel content."""
    filename = ("_".join(name_bits) + "." + name_extension).replace(" ", "_")
    response = HttpResponse(content_type=mime_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(content)
    return response


def view_delivery_purchases_html(request, delivery):
    """View all purchases for a given delivery. Network staff only."""
    delivery = Delivery.objects.get(id=delivery)
    subgroups = delivery.network.subgroup_set.all()
    return render_to_response('view_purchases.html', delivery_description(delivery, subgroups))


def view_delivery_purchases_xlsx(request, delivery):
    """View all purchases for a given delivery in an MS-Excel spreadsheet. Network staff only."""
    delivery = Delivery.objects.get(id=delivery)
    subgroups = delivery.network.subgroup_set.all()
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet(delivery, subgroups))


def view_delivery_purchases_pdf(request, delivery):
    """View the purchases of each subgroup as an Adobe PDF file. Subgroup staff only."""
    delivery = Delivery.objects.get(id=delivery)
    return _non_html_response((delivery.network.name, delivery.name), "pdf",
                              "application/pdf",
                              pdf.all(delivery))


def view_subgroup_purchases_html(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = Delivery.objects.get(id=delivery)
    subgroup = get_subgroup(request, delivery.network)
    return render_to_response('view_purchases.html',
                              delivery_description(delivery, [subgroup]))


def view_subgroup_purchases_xlsx(request, delivery):
    """View the purchases of a subgroup as an MS-Excel file. Subgroup staff only."""
    delivery = Delivery.objects.get(id=delivery)
    subgroup = get_subgroup(request, delivery.network)
    return _non_html_response((delivery.network.name, delivery.name, subgroup.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet(delivery, [subgroup]))


def view_subgroup_purchases_pdf(request, delivery):
    """View the purchases of a subgroup as an Adobe PDF file. Subgroup staff only."""
    delivery = Delivery.objects.get(id=delivery)
    subgroup = get_subgroup(request, delivery.network)
    return _non_html_response((delivery.network.name, delivery.name, subgroup.name), "pdf",
                              "application/pdf",
                              pdf.subgroup(delivery, subgroup))
