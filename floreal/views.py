#!/usr/bin/python
# -*- coding: utf8 -*-

from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.core.context_processors import csrf
from django.contrib.auth.decorators import login_required

from . import models as m
from .spreadsheet import spreadsheet
from . import pdf
from . import edit_delivery_view
from delivery_table_view import delivery_description
from parse_subgroup_purchases import parse_subgroup_purchases
from parse_user_purchases import parse_user_purchases

@login_required()
def index(request):
    """Main page: sum-up of current deliveries, links to active pages."""
    user = request.user
    user_subgroups = m.Subgroup.objects.filter(users__in=[user])
    user_networks = [s.network for s in user_subgroups]
    user_deliveries = m.Delivery.objects.filter(network__in=user_networks)
    user_orders = [m.Order(user, delivery) for delivery in user_deliveries]
    staffed_networks = m.Network.objects.filter(staff__in=[user])
    staffed_subgroups = m.Subgroup.objects.filter(staff__in=[user])
    # TODO: reintegrate subgroup staff entries with network staff entries,
    # TODO: when current user is net-staff and group-staff in the same network
    vars = {
        'user': user,
        'as_user': {
            'open': [order.delivery for order in user_orders
                                    if not order.purchases
                                    and order.delivery.state == m.Delivery.OPEN],
            'modifiable': [order for order in user_orders
                                 if order.purchases
                                 and order.delivery.state == m.Delivery.OPEN],
            'past': [order for order in user_orders
                           if order.delivery.state != m.Delivery.OPEN],
        },
        'as_staff': {
            'networks': [(n, n.delivery_set.all()) for n in staffed_networks],
            'subgroups': [(s, s.network.delivery_set.filter(state=m.Delivery.OPEN)) for s in staffed_subgroups]
        }
    }
    return render_to_response('index_logged.html', vars)


def create_delivery(request, network):
    """Create a new delivery, then redirect to its edition page."""
    network = m.Network.objects.get(id=network)
    months = [u'Janvier', u'Février', u'Mars', u'Avril', u'Mai', u'Juin', u'Juillet',
              u'Août', u'Septembre', u'Octobre', u'Novembre', u'Décembre']
    now = datetime.now()
    name = '%s %d' % (months[now.month-1], now.year)
    d = m.Delivery.objects.create(network=network, name=name, state=m.Delivery.CLOSED)
    d.save()
    return redirect('edit_delivery_products', delivery=d.id)


def set_delivery_state(request, delivery, state):
    """Change a delivery's state between "Open", "Closed" and "Delivered"."""
    delivery = m.Delivery.objects.get(id=delivery)
    [state_code] = [code for (code, name) in m.Delivery.STATE_CHOICES if name==state]
    delivery.state = state_code
    delivery.save()
    return redirect('index')


def edit_delivery_products(request, delivery):
    """Edit a delivery (name, state, products). Network staff only."""

    delivery = get_object_or_404(m.Delivery, pk=delivery)

    if request.method == 'POST':  # Handle submitted data
        edit_delivery_view.parse_form(request)
        return redirect('index')

    else:  # Create and populate forms to render
        vars = edit_delivery_view.make_form(delivery)
        vars['user'] = request.user
        vars.update(csrf(request))
        return render_to_response('edit_delivery.html', vars)


def _non_html_response(name_bits, name_extension, mime_type, content):
    """Common helper to serve PDF and Excel content."""
    filename = ("_".join(name_bits) + "." + name_extension).replace(" ", "_")
    response = HttpResponse(content_type=mime_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(content)
    return response


def view_delivery_purchases_html(request, delivery):
    """View all purchases for a given delivery. Network staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroups = delivery.network.subgroup_set.all()
    return render_to_response('view_purchases.html', delivery_description(delivery, subgroups))


def view_delivery_purchases_xlsx(request, delivery):
    """View all purchases for a given delivery in an MS-Excel spreadsheet. Network staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroups = delivery.network.subgroup_set.all()
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet(delivery, subgroups))


def view_subgroup_purchases_html(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])

    return render_to_response('view_purchases.html',
                              delivery_description(delivery, [subgroup]))


def view_subgroup_purchases_xlsx(request, delivery):
    """View the purchases of a subgroup as an MS-Excel file. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])
    return _non_html_response((delivery.network.name, delivery.name, subgroup.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet(delivery, [subgroup]))


def view_subgroup_purchases_pdf(request, delivery):
    """View the purchases of a subgroup as an Adobe PDF file. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])
    return _non_html_response((delivery.network.name, delivery.name, subgroup.name), "pdf",
                              "application/pdf",
                              pdf.subgroup(delivery, subgroup))


def edit_subgroup_purchases(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])
    if request.method == 'POST':
        if parse_subgroup_purchases(request):
            redirect("index")
        else:
            #TODO: display errors in template
            redirect("edit_subgroup_purchases", delivery=delivery.id)
    else:
        return render_to_response('edit_subgroup_purchases.html',
                                  delivery_description(delivery, [subgroup], user=user))


def edit_user_purchases(request, delivery):
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    order = m.Order(user, delivery)
    if request.method == 'POST':
        if parse_user_purchases(request):
            return redirect("index")
        else:
            #TODO: display errors in template
            return redirect("edit_user_purchases", delivery=delivery.id)
    else:
        vars = {
            'user': user,
            'delivery': delivery,
            'subgroup': delivery.network.subgroup_set.get(staff__in=[user]),
            'products': m.Product.objects.filter(delivery=delivery),
            'purchases': order.purchases
        }
        vars.update(csrf(request))
        return render_to_response('edit_user_purchases.html', vars)

