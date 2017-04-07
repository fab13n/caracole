#!/usr/bin/python
# -*- coding: utf-8 -*-

from decimal import Decimal

from django.shortcuts import redirect, render_to_response
from django.core.context_processors import csrf
from django.contrib.auth.decorators import login_required

from .. import models as m
from ..penury import set_limit
from .delivery_description import delivery_description
from .getters import get_subgroup
from .decorators import sg_admin_required


@sg_admin_required()
def adjust_subgroup(request, delivery, subgroup=None):
    """Adjust the totals ordered by a subgroup."""
    dv = m.Delivery.objects.get(id=delivery)
    if request.method == 'POST':  # Parse response
        if _parse_form(request):
            return redirect("index")
        else:  # Generate page
            # TODO: display errors in template
            return redirect("subgroup_regulation", delivery=dv.id)
    else:
        sg = get_subgroup(subgroup)
        dd = delivery_description(dv, [sg])
        vars = {
            'delivery': dv,
            'subgroup': sg,
            'products': [{'pd': pt['product'], 'ordered': pt['quantity']} for pt in dd['product_totals']],
        }
        for pt in vars['products']:
            try:
                ds = m.Discrepancy.objects.get(product=pt['pd'], subgroup=sg)
                pt['delivered'] = pt['ordered'] + ds.amount
                pt['reason'] = ds.reason
            except m.Discrepancy.DoesNotExist:
                pt['delivered'] = pt['ordered']
        vars.update(csrf(request), user=request.user)
        return render_to_response('regulation.html', vars)


def _parse_form(request):
    """
    Parse response: compute the amount of extra orders needed to reach the required total.
    """
    d = request.POST
    dv = m.Delivery.objects.get(pk=int(d['dv-id']))
    sg = m.Subgroup.objects.get(pk=int(d['sg-id']))
    dd = delivery_description(dv, [sg])
    totals_before = dd['table'][0]['totals']
    for i, pd in enumerate(dd['products']):
        total_before = totals_before[i]['quantity']
        total_after = Decimal(d["pd%s-delivered-total" % pd.id])
        amount = total_after - total_before
        if amount:
            print "Quantity of %s adjusted from %s to %s" % (pd.name, total_before, total_after)
            reason = d['pd%s-reason' % pd.id]
            set_discrepancy(pd, sg, amount, reason)

    if dv.get_stateForSubgroup(sg) < m.SubgroupStateForDelivery.READY_FOR_ACCOUNTING:
        dv.set_stateForSubgroup(sg, m.SubgroupStateForDelivery.READY_FOR_ACCOUNTING)
        m.JournalEntry.log(request.user, "Subgroup %s/%s regularized accounting for delivery %s",
                           dv.network.name, sg.name, dv.name)

    return True  # true == no error

def set_discrepancy(pd, sg, amount, reason):
    m.Discrepancy.objects.filter(product=pd, subgroup=sg).delete()
    if amount != 0:
        m.Discrepancy.objects.create(product=pd, subgroup=sg, amount=amount, reason=reason)
