#!/usr/bin/python
# -*- coding: utf8 -*-

from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from . import models as m
from . import spreadsheet
from . import pdf

def index(request):
    """Main page: sum-up of current deliveries, links to active pages."""
    user = request.user
    user_subgroups = m.Subgroup.objects.filter(users__in=[user])
    user_networks = [s.network for s in user_subgroups]
    user_deliveries = m.Delivery.objects.filter(network__in=user_networks)
    user_orders = [m.Order(user, delivery) for delivery in user_deliveries]
    staffed_networks = m.Network.objects.filter(staff__in=[user])
    staffed_subgroups = m.Subgroup.objects.filter(staff__in=[user])
    vars = {
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
    d = m.Delivery.create(network=network, name=name, state=m.Delivery.CLOSED)
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
    delivery = m.Delivery.objects.get(id=delivery)
    vars = { }
    return render_to_response('edit_delivery_products.html', vars)


def _non_html_response(name_bits, name_extension, mime_type, content):
    """Common helper to serve PDF and Excel content."""
    filename = "_".join(name_bits) + "." + name_extension
    response = HttpResponse(content_type=mime_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(content)
    return response


def view_delivery_purchases_html(request, delivery):
    """View all purchases for a given delivery. Network staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroups = delivery.network.subgroup_set
    users = m.User.objects\
        .filter(user_of__in=subgroups)\
        .order_by('last_name', 'first_name')
    products = delivery.product_set.order_by('name')
    orders_by_user = m.Order.by_user_and_product(delivery, users, products)
    orders_by_subgroup = {s: {} for s in subgroups}
    for u, orders in orders_by_subgroup.iteritems():
        orders[u] = orders_by_user[u]

    vars = {
        'delivery': delivery,
        'products': products,
        'orders': orders_by_subgroup
    }
    return render_to_response('view_delivery_purchases.html', vars)


def view_delivery_purchases_xlsx(request, delivery):
    """View all purchases for a given delivery in an MS-Excel spreadsheet. Network staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet.all(delivery))


def view_subgroup_purchases_html(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])

    products = delivery.product_set.order_by('name')
    users = subgroup.users.order_by('last_name', 'first_name')
    orders = m.Order.by_user_and_product(delivery, users, products)

    # Compute quantities per product 1: initialize
    totals_by_product = {pd: {
        'quantity': 0,
        'product': pd
    } for pd in products}

    # Compute quantities per product 2: add up quantities
    for o in orders.itervalues():
        for pc in o.purchases:
            if pc:
                totals_by_product[pc.product]['quantity'] += pc.granted

    # Compute quantities per product 3: count packages
    for pd, count in totals_by_product.iteritems():
        qpp = pd.quantity_per_package
        if qpp:
            count['full_packages'] = count['quantity'] // qpp
            count['out_of_packages'] = count['quantity'] % qpp

    # Compute quantities per product 4: dict -> sorted list
    totals_by_product=totals_by_product.items()
    def cmp_product_items(item):
        (k, v) = item
        return k.name
    totals_by_product.sort(cmp=cmp_product_items)
    totals_by_product = [v for k, v in totals_by_product]

    # Orders: user/order dict -> order list sorted by user name
    orders = orders.values()
    orders.sort(key=lambda o: o.user.last_name+' '+o.user.first_name)

    vars = {
        'delivery': delivery,
        'subgroup': subgroup,
        'products': products,
        'orders': orders,
        'totals_by_product': totals_by_product,
        'total_price': sum(o.price for o in orders)
    }
    return render_to_response('view_subgroup_purchases.html', vars)


def view_subgroup_purchases_xlsx(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet.subgroup(delivery, subgroup))


def view_subgroup_purchases_pdf(request, delivery):
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              pdf.subgroup(delivery, subgroup))


def edit_subgroup_purchases(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])
    vars = { }
    return render_to_response('view_subgroup_purchases.html', vars)


def edit_user_purchases(request, delivery):
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    vars = { }
    return render_to_response('edit_user_purchases.html', vars)

