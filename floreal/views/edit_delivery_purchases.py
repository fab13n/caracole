#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re

import django
from django.template.context_processors import csrf
from django.shortcuts import redirect, render
from django.http import HttpResponseForbidden

from .. import models as m
from ..penury import set_limit
from .getters import get_network, get_delivery
from .decorators import regulator_required

def edit_delivery_purchases(request, delivery):
    """Allows to change the purchases of user's subgroup. Subgroup staff only."""
    user = request.user
    dv = get_delivery(delivery)

    if user not in dv.network.staff and user not in dv.network.producers:
        return HttpResponseForbidden(f"Réservé aux admins et producteurs du réseau {dv.network.name}")

    if request.method == 'POST':
        _parse_form(request, dv, nw)
        return redirect("view_delivery_purchases_html", delivery=dv.id, network=nw.id)
    else:
        vars = {'user': user, 'delivery': dv}
        vars.update(csrf(request))
        return render(request,'edit_delivery_purchases.html', vars)


def _parse_form(request, dv, nw):
    """
    Parse responses from subgroup purchase editions.
    :param request:
    :return:
    """

    d = request.POST.dict()

    mods = []

    for name, value in d.items():
        bits = name.split('-')
        if len(bits) == 4 and bits[0] == 'pd' and bits[2] == 'u':
            pd_id = int(bits[1])
            u_id = int(bits[3])
            q = float(value.replace(",", "."))
            mods.append((pd_id, u_id, q))

    if not mods:
        return True

    # TODO Check that every user is in that network

    print("MODS:", mods)

    check_quotas = set()  # Products which might have gone over quota

    for pd_id, u_id, q in mods:
        pc = m.Purchase.objects.filter(product_id=pd_id, user_id=u_id).first()
        if pc is None:  # Create purchase
            pd = m.Product.objects.get(id=pd_id)
            assert dv.id == pd.delivery_id
            m.Purchase.objects.create(product_id=pd_id, user_id=u_id, quantity=q)
            check_quotas.add(pd)
        elif q == 0.:  # Delete purchase
            assert pc.product.delivery_id == dv.id
            pc.delete()
        else:  # Modify existing purchase
            assert pc.product.delivery_id == dv.id
            pc.quantity = q
            pc.save()
            check_quotas.add(pc.product)

    if check_quotas:
        for pd in check_quotas:
            set_limit(pd)
    
    m.JournalEntry.log(request.user, "Modified user purchases in dv-%d nw-%d", dv.id, nw.id)

    return True  # true == no error
