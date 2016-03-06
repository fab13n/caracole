#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.shortcuts import redirect, render_to_response
from django.core.context_processors import csrf
from decimal import Decimal

from .. import models as m
from ..penury import set_limit
from .delivery_description import delivery_description
from .view_purchases import get_subgroup


def adjust_subgroup(request, delivery, subgroup=None):
    """Adjust the totals ordered by a subgroup."""
    delivery = m.Delivery.objects.get(id=delivery)
    if request.method == 'POST':
        if _parse_form(request):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("adjust_subgroup", delivery=delivery.id)
    else:
        if not subgroup: subgroup = get_subgroup(request, delivery.network)
        vars = delivery_description(delivery, [subgroup])
        vars.update(csrf(request), user=request.user)
        return render_to_response('adjust_subgroup.html', vars)


def _parse_form(request):
    """
    Parse response: compute the amount of extra orders needed to reach the required total.
    """
    d = request.POST
    dv = m.Delivery.objects.get(pk=int(d['dv-id']))
    subgroup = get_subgroup(request, dv.network)
    dd = delivery_description(dv, [subgroup])
    totals_before = dd['table'][0]['totals']
    extra_purchases = {pc.product.id: pc for pc in m.Order(subgroup.extra_user, dv).purchases}
    for i, pd in enumerate(dd['products']):
        total_before = totals_before[i]['quantity']
        total_after = Decimal(d["pd%s" % pd.id])
        delta = total_after - total_before
        pc = extra_purchases.get(pd.id, False)
        print "Quantity of %s adjusted from %s to %s" % (pd.name, total_before, total_after)
        if not delta:
            continue
        elif pc:
            pc.ordered += delta
            pc.save()
        else:  # Adjustment required, no previous extra purchase: create it
            pc = m.Purchase.objects.create(user=subgroup.extra_user, product=pd, ordered=delta, granted=delta)
    set_limit(pd)  # In case of penury

    return True  # true == no error
