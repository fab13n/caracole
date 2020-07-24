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
from floreal.views.dd2 import DeliveryDescription

@regulator_required()
def edit_delivery_purchases(request, delivery, network):
    """Allows to change the purchases of user's subgroup. Subgroup staff only."""
    user = request.user
    dv = get_delivery(delivery)
    nw = get_network(network)


    if nw.staff.filter(id=user.id).exists() or nw.regulators.filter(id=user.id).exists():
        return HttpResponseForbidden(f"Réservé aux admins et régulateure du réseau {nw.name}")

    if request.method == 'POST':
        _parse_form(request)
        return redirect("view_delivery_purchases_html", delivery=delivery.id, network=network)
    else:
        vars = {'dd': DeliveryDescription(dv, networks=[nw])}
        vars.update(csrf(request))
        return render(request,'edit_delivery_purchases.html', vars)


def _parse_form(request):
    """
    Parse responses from subgroup purchase editions.
    :param request:
    :return:
    """

    d = request.POST
    pd_u_mods = re.findall(r'pd(\d+)u(\d+)', d['modified'])
    for pd, u in pd_u_mods:
        ordered = float(d['pd%su%s' % (pd, u)])
        try:
            pc = m.Purchase.objects.get(product_id=pd, user_id=u)
            if ordered != 0:
                # print("Updating purchase %d" % pc.id)
                pc.quantity = ordered
                pc.save(force_update=True)
            else:
                # print "Cancelling purchase %d" % pc.id
                pc.delete()
        except m.Purchase.DoesNotExist:
            if ordered != 0:
                # print "Creating purchase for pd=%s, u=%s, q=%f" % (pd, u, ordered)
                pc = m.Purchase.objects.create(product_id=pd, user_id=u, quantity=ordered)
            else:
                pc = None
        # Update ordered / granted mismatches in case of product penury, for every purchase
        if pc:
            set_limit(pc.product)
        dv = m.Delivery.objects.get(id=d['dv-id'])
        m.JournalEntry.log(request.user, "Modified %d user purchases in dv-%d %s/%s",
                           len(pd_u_mods), dv.id, dv.network.name, dv.name)

    return True  # true == no error
