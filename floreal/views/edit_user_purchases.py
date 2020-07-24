#!/usr/bin/python3
# -*- coding: utf-8 -*-

import django
if django.VERSION < (1, 8):
    from django.core.context_processors import csrf
else:
    from django.template.context_processors import csrf
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .. import models as m
from ..penury import set_limit
from .getters import get_delivery


@login_required()
def edit_user_purchases(request, delivery):
    """Let user order for himself, or modified an order on an open delivery."""
    delivery = get_delivery(delivery)
    user = request.user
    if delivery.state != delivery.ORDERING_ALL:
        return HttpResponseForbidden("Cette commande n'est pas ouverte.")
    if request.method == 'POST':
        if _parse_form(request):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_purchases", delivery=delivery.id)
    else:
        purchases = m.Purchase.objects.filter(product__delivery=delivery, user=user)
        some_packaged = any(pc.product.quantity_per_package is not None for pc in purchases)
        for pc in purchases:
            pc.described = (pc.product.description or pc.product.image) and pc.max_quantity != 0
        vars = {
            'user': user,
            'delivery': delivery,
            'network': delivery.networks.filter(members__in=[user]).first(),
            'purchases': purchases,
            'some_packaged': some_packaged,
            'out_of_stock_colspan': 6 if some_packaged else 5,
            'total_padding_right_colspan': 2 if some_packaged else 1,
            'description_colspan': 7 if some_packaged else 6,
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
    od = m.Order(request.user, dv, with_dummies=True)
    prev_purchases = {pc.product: pc for pc in od.purchases}
    for pd in dv.product_set.all():
        try:
            ordered = float(d.get("pd%s" % pd.id, "0"))
        except ValueError:  # Field present, didn't contain a valid float
            continue
        pc = prev_purchases[pd]
        if pc.quantity == ordered:  # No change
            pass
        elif ordered == 0:  # Cancel existing purchase
            pc.delete()
        elif pc.quantity == 0:  # Create a non-dummy purchase
            pc = m.Purchase.objects.create(user=request.user, product=pd, quantity=ordered)
            set_limit(pd, last_pc=pc)  # In case of penury
        else:  # Update existing purchase quantity
            pc.quantity = ordered
            pc.save()
            set_limit(pd, last_pc=pc)  # In case of penury

    m.JournalEntry.log(request.user, "Modified their purchases for dv-%d %s/%s", dv.id, dv.network.name, dv.name)
    return True  # true == no error
