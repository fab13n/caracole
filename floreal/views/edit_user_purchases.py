#!/usr/bin/python3
# -*- coding: utf-8 -*-

import django
if django.VERSION < (1, 8):
    from django.core.context_processors import csrf
else:
    from django.template.context_processors import csrf
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from .. import models as m
from ..penury import set_limit
from .getters import get_delivery


@login_required()
def edit_user_purchases(request, delivery):
    """Let user order for himself, or modified an order on an open delivery."""
    delivery = get_delivery(delivery)
    user = request.user
    order = m.Order(user, delivery)
    if request.method == 'POST':
        if _parse_form(request):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_purchases", delivery=delivery.id)
    else:
        products = m.Product.objects.filter(delivery=delivery)
        vars = {
            'QUOTAS_ENABLED': True,
            'user': user,
            'delivery': delivery,
            'subgroup': delivery.network.subgroup_set.get(users__in=[user]),
            'products': products,
            'purchases': order.purchases
        }
        vars.update(csrf(request))
        return render(request,'edit_user_purchases.html', vars)


def _parse_form(request):
    """
    Parse responses from user purchases.
    :param request:
    :return:
    """
    d = request.POST
    dv = m.Delivery.objects.get(pk=int(d['dv-id']))
    od = m.Order(request.user, dv)
    prev_purchases = {pc.product: pc for pc in od.purchases}
    for pd in dv.product_set.all():
        ordered = float(d["pd%s" % pd.id])
        if ordered <= 0 and pd not in prev_purchases:
            continue
        if pd in prev_purchases:
            pc = prev_purchases[pd]
        else:
            pc = m.Purchase.objects.create(user=request.user, product=pd, quantity=0)
        if ordered <= 0:
            pc.delete()
        else:
            pc.quantity = ordered
            pc.save()
        set_limit(pd)  # In case of penury

    m.JournalEntry.log(request.user, "Modified their purchases for %s/%s", dv.network.name, dv.name)

    return True  # true == no error
