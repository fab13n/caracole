#!/usr/bin/python
# -*- coding: utf8 -*-

"""Helpers to edit products list: generate suggestions based on current and
past products, parse POSTed forms to update a delivery's products list."""

from .models import Product, Delivery


def _get_products_list(delivery):
    """All products in the current delivery, plus products of past deliveries
    in this network whose name doesn't occur in current delivery. When several
    products with the same name exist in the past, the most recent one is kept."""

    current_products = delivery.product_set.order_by('-id')
    current_names_set = {pd.name for pd in current_products}
    past_products = [Product.objects\
                         .filter(name=x['name'], delivery__network=delivery.network)\
                         .order_by('-id')[0]
                     for x in Product.objects.values('name').distinct()]
    non_overridden_past_products = [pd for pd in past_products if pd.name not in current_names_set]
    return list(current_products) + non_overridden_past_products


def make_form(delivery):
    return {'delivery': delivery,
            'products': _get_products_list(delivery)}


def _get_pd_fields(d, prefix, id):
    """Retrieve form fields representing a product."""
    fields = ['name', 'price', 'quantity_per_package', 'unit', 'quantity_limit']
    raw = {f: d["%s%d-%s" % (prefix, id, f)] for f in fields}
    if not any(f for f in raw.values()):
        return { 'deleted': True }  # All fields empty means deleted
    qpp = raw['quantity_per_package']
    quota = raw['quantity_limit']
    return {'name': raw['name'],
            'price': float(raw['price']),
            'quantity_per_package': int(qpp) if qpp else None,
            'unit': raw['unit'],
            'quantity_limit': int(quota) if quota else None,
            'deleted': "%s%d-deleted" % (prefix, id) in d }


def _pd_update(pd, fields):
    """Update a model object according to form fields."""
    pd.name = fields['name']
    pd.price = fields['price']
    quantity_per_package = fields['quantity_per_package']
    pd.unit = fields['unit']
    quantity_limit = fields['quantity_limit']


def parse_form(request):
    """Parse a delivery edition form and update DB accordingly."""
    d = request.POST
    print(d)
    dv = Delivery.objects.get(pk=int(d['dv-id']))

    # Edit delivery name and state
    dv.name = d['dv-name']
    dv.state = d['dv-state']
    dv.save()

    # Parse preexisting products
    product_ids_string = str(d['product_ids'])
    if product_ids_string:
        for pd_id in product_ids_string.split(','):
            pd = Product.objects.get(pk=pd_id)
            fields = _get_pd_fields(d, 'pd', int(pd_id))
            if pd.delivery == dv:
                if fields['deleted']:  # Delete previously existing product
                    print "Deleting product %s" % pd_id
                    pd.delete()
                else:  # Update product
                    print "Updating product %s" % pd_id
                    _pd_update(pd, fields)
                    pd.save(force_update=True)
            else:  # From another delivery
                if fields['deleted']:  # Don't import product
                    print "Ignoring past product %s" % pd_id
                    pass
                else:  # Import product copy from other delivery
                    print "Importing past product %s" % pd_id
                    _pd_update(pd, fields)
                    pd.delivery = dv
                    pd.save(force_create=True)

    # Parse products created from blank lines
    for i in range(int(d['n_blanks'])):
        # Create new product
        fields =  _get_pd_fields(d, 'blank', i)
        if fields['deleted']:
            print "Blank field #%d deleted/empty" % i
        else:
            print "Adding product from blank line #%d" % i
            pd = Product.objects.create(name=fields['name'],
                                        price=fields['price'],
                                        quantity_per_package=fields['quantity_per_package'],
                                        quantity_limit=fields['quantity_limit'],
                                        unit=fields['unit'],
                                        delivery=dv)
            pd.save()
