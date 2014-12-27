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
    # TODO: reintegrate subgroup staff entries with network staff entries,
    # TODO: when current user is net-staff and group-staff in the same network
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


def _delivery_description(delivery, subgroups):
    """Generate a description of the purchases performed by users in `subgroups`
    for `delivery`. The resulting dictionary is used to render HTML as well as
    PDF and MS-Excel views. It's used both to display the complete order to network staff,
    and their subgroup's purchases to subgroup staff (in this case `subgroups` is expected
    to have only one element).

    The resulting dictionaty is structured as follows, with many data organized by numeric
    indexes rather than hashtables in order to ease tabular rendering:

        { "delivery": delivery,
          "products": product_idx -> product,
          "table": subgroup_idx -> { "subgroup": subgroup,
                                     "totals": product_idx -> { "product": product,
                                                                "quantity": number,
                                                                "full_packages": number,
                                                                "out_of_packages": number }.
                                     "users": user_idx -> { "user": user,
                                                            "orders": product_idx -> order.
                                                             "price": number},
                                     "price": number },
          "product_totals": productPidx -> { "product": product,
                                             "quantity": number,
                                             "full_packages": number,
                                             "out_of_packages": number },
          "price": number }
    """
    # List of products, ordered by name
    products = delivery.product_set.order_by('name')
    # Iterable of all users in subgroups
    users = m.User.objects.filter(user_of__in=subgroups)
    # Dictionary user -> list of ordered, indexed as products
    orders = m.Order.by_user_and_product(delivery, users, products)

    # Compute totals per product per subgroup 1: initialize
    # Dictionary subgroup -> product -> { product, granted_quantity }
    sg_pd_totals = {
        sg: {
            pd: {
                'product': pd,
                'quantity': 0,
            } for pd in products
        } for sg in subgroups
    }
    sg_price = {sg: 0 for sg in subgroups}

    # Generate user->subgroup dict, helper to compute totals per subgroup
    user_to_subgroup = {}
    for s in subgroups:
        for u in s.users.iterator():
            user_to_subgroup[u] = s

    # Sum quantities per subgroup and per product;
    for o in orders.itervalues():
        s = user_to_subgroup[o.user]
        for pc in o.purchases:
            if pc:
                sg_pd_totals[s][pc.product]['quantity'] += pc.granted

    # Break up quantities in packages + loose items
    for pd_totals in sg_pd_totals.itervalues():
        for pd, totals in pd_totals.iteritems():
            qty = totals['quantity']
            qpp = pd.quantity_per_package
            if qpp:
                totals['full_packages'] = qty // qpp
                totals['out_of_packages'] = qty % qpp

    # Sum up grand total (all subgroups together) per product
    product_totals = []
    for i, pd in enumerate(products):
        qty = sum(sg_pd_totals[sg][pd]['quantity'] for sg in subgroups)
        qpp = pd.quantity_per_package
        total = {'product': pd, 'quantity': qty}
        if qpp:
            total['full_packages'] = qty // qpp
            total['out_of_packages'] = qty % qpp
        product_totals.append(total)

    # Convert dictionaries into ordered lists in `table`:
    # subgroup_idx -> { "subgroup": subgroup,
    #                   "totals": product_idx -> { "product": product,
    #                                              "quantity": number,
    #                                              "full_packages": number,
    #                                              "out_of_packages": number }.
    #                   "users": user_idx -> { "user": user,
    #                                          "orders": product_idx -> order.
    #                                          "price": number },
    #                   "price": number }
    table = []
    for i, sg in enumerate(subgroups):
        pd_totals = sg_pd_totals[sg]
        pd_totals_list = []
        user_orders = []
        sg_item = {'subgroup': sg, 'totals': pd_totals_list, 'users': user_orders}
        table.append(sg_item)
        for j, pd in enumerate(products):
            pd_totals_list.append(pd_totals[pd])
        for k, u in enumerate(s.users.order_by('last_name', 'first_name')):
            order = orders[u]
            user_orders.append({
                'user': u,
                'orders': order,
                'price': sum(pc.price for pc in order.purchases if pc)})
        sg_item['price'] = sum(uo['price'] for uo in user_orders)

    price = sum(x['price'] for x in table)

    return {
        'delivery': delivery,
        'products': products,
        'product_totals': product_totals,
        'table': table,
        'price': price
    }


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
    subgroups = delivery.network.subgroup_set.all()
    return render_to_response('view_purchases.html', _delivery_description(delivery, subgroups))


def view_delivery_purchases_xlsx(request, delivery):
    """View all purchases for a given delivery in an MS-Excel spreadsheet. Network staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet.all(delivery))


def view_subgroup_purchases_html(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])

    return render_to_response('view_purchases.html',
                              _delivery_description(delivery, [subgroup]))


def view_subgroup_purchases_xlsx(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              spreadsheet.subgroup(_subgroup_purchases_vars(delivery, user)))



def view_subgroup_purchases_pdf(request, delivery):
    delivery = m.Delivery.objects.get(id=delivery)
    subgroup = delivery.network.subgroup_set.get(staff__in=[request.user])
    return _non_html_response((delivery.network.name, delivery.name), "xlsx",
                              "application/pdf",
                              pdf.subgroup(_subgroup_purchases_vars(delivery, user)))


def edit_subgroup_purchases(request, delivery):
    """View the purchases of a subgroup. Subgroup staff only."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    subgroup = delivery.network.subgroup_set.get(staff__in=[user])
    vars = { }
    return render_to_response('edit_subgroup_purchases.html', vars)


def edit_user_purchases(request, delivery):
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    vars = { }
    return render_to_response('edit_user_purchases.html', vars)

