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



def parse_form(request):
    d = request.POST
    print(d.__dict__)
    dv = Delivery.objects.get(pk=int(d['dv-id']))
    for pd_id in str(d['product_ids']).split(','):
        pd = Product.objects.get(pk=pd_id)
        if pd.delivery == dv:
            if d.get('pd%s-deleted' % pd_id, False):  # Delete previously existing product
                print "Deleting product %s" % pd_id
            else:  # Update product
                print "Updating product %s" % pd_id
        else:
            if d.get('pd%s-deleted' % pd_id, False):  # Import product copy from other delivery
                print "Importing past product %s" % pd_id
            else:  # Don't import product
                print "Ignoring past product %s" % pd_id
