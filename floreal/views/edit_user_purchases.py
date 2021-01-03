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
    """Let user order for himself, or modify an order on an open delivery."""
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
        vars = {
            'delivery': delivery,
        }
        vars.update(csrf(request))
        return render(request,'edit_user_purchases.html', vars)


def _parse_form(request):
    """
    Parse responses from user purchases.
    :param request:
    :return:
    """
    d = request.POST.dict()
    dv = m.Delivery.objects.get(id=int(d['delivery-id']))
    quantities = { } # pd.id -> quantity
    for name, val in d.items():
        bits = name.split("-")
        if bits[0] == "pd" and bits[1].isdigit():
            quantities[int(bits[1])] = float(val)
            # TODO check quantum
    previous_purchases = {
        pc.product.id: pc
        for pc in m.Purchase.objects.filter(product__delivery=dv, user=request.user)
    }

    for pd in dv.product_set.all():
        ordered = quantities.get(pd.id)
        if ordered is None:  # Typically because pd was out of order
            continue

        pc = previous_purchases.get(pd.id)
   
        if ordered == 0 and pc is None:  # Still not ordered
            continue
        elif pc is None: # New order
            pc = m.Purchase.objects.create(user=request.user, product=pd, quantity=ordered)
        elif ordered == pc.quantity:  # Unchanged order
            continue
        elif ordered == 0:  # Cancelled order
            pc.delete()
        else:  # Modified order
            pc.quantity = ordered
            pc.save()
        set_limit(pd, last_pc=pc)

    m.JournalEntry.log(request.user, "Modified their purchases for dv-%d", dv.id)
    return True  # true == no error
