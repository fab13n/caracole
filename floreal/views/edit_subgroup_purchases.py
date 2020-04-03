#!/usr/bin/python
# -*- coding: utf-8 -*-

import re

import django
if django.VERSION < (1, 8):
    from django.core.context_processors import csrf
else:
    from django.template.context_processors import csrf
from django.shortcuts import redirect, render_to_response
from django.http import HttpResponseForbidden

from .. import models as m
from ..penury import set_limit
from .delivery_description import delivery_description
from .getters import get_subgroup, get_delivery
from .decorators import sg_admin_required


@sg_admin_required()
def edit_subgroup_purchases(request, delivery, subgroup):
    """Allows to change the purchases of user's subgroup. Subgroup staff only."""
    delivery = get_delivery(delivery)
    user = request.user
    subgroup = get_subgroup(subgroup)

    if user not in subgroup.staff.all() and user not in delivery.network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + delivery.network.name + \
                                     ' ou du sous-groupe '+subgroup.name)

    if request.method == 'POST':
        _parse_form(request)
        return redirect("view_subgroup_purchases_html", delivery=delivery.id, subgroup=subgroup.id)
    else:
        vars = delivery_description(delivery, [subgroup], user=user)
        vars.update(csrf(request))
        return render_to_response('edit_subgroup_purchases.html', vars)


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
                # print "Updating purchase %d" % pc.id
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
        m.JournalEntry.log(request.user, "Modified %d user purchases in %s/%s",
                           len(pd_u_mods), dv.network.name, dv.name)

    return True  # true == no error
