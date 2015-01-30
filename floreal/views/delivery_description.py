#!/usr/bin/python
# -*- coding: utf-8 -*-

from floreal import models as m


def delivery_description(delivery, subgroups, **kwargs):
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
                                                                "out_of_packages": number,
                                                                "weight": number },
                                     "users": user_idx -> { "user": user,
                                                            "orders": product_idx -> order,
                                                            "price": number,
                                                            "weight": number },
                                     "price": number,
                                     "weight": number},
          "product_totals": product_idx -> { "product": product,
                                             "quantity": number,
                                             "full_packages": number,
                                             "out_of_packages": number },
          "price": number }
    """
    # List of products, ordered by name
    products = delivery.product_set.all()
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

    # Generate user->subgroup dict, helper to compute totals per subgroup
    user_to_subgroup = {}
    for sg in subgroups:
        for u in sg.users.iterator():
            user_to_subgroup[u] = sg

    # Sum quantities per subgroup and per product;
    for od in orders.itervalues():
        sg = user_to_subgroup[od.user]
        for pc in od.purchases:
            if pc:
                sg_pd_totals[sg][pc.product]['quantity'] += pc.granted

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
    #                                          "price": number,
    #                                          "weight": number },
    #                   "price": number,
    #                   "weight": number }
    table = []
    for i, sg in enumerate(subgroups):
        pd_totals = sg_pd_totals[sg]
        pd_totals_list = []
        user_records = []
        # Get and order users alphabetically, except for the extra user which gets last
        sg_item = {'subgroup': sg, 'totals': pd_totals_list, 'users': user_records}
        table.append(sg_item)
        for j, pd in enumerate(products):
            pd_totals_list.append(pd_totals[pd])
        for k, u in enumerate(sg.sorted_users):
            order = orders[u]
            user_records.append({
                'user': u,
                'orders': order,
                'price': sum(pc.price for pc in order.purchases if pc),
                'weight': sum(pc.weight for pc in order.purchases if pc)})
        sg_item['price'] = sum(uo['price'] for uo in user_records)
        sg_item['weight'] = sum(uo['weight'] for uo in user_records)

    price = sum(x['price'] for x in table)

    result = {
        'delivery': delivery,
        'products': products,
        'product_totals': product_totals,
        'table': table,
        'price': price
    }
    result.update(kwargs)
    return result
