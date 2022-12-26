#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re

import django
from django.template.context_processors import csrf
from django.shortcuts import redirect, render
from django.core.exceptions import PermissionDenied

from .. import models as m
from ..penury import set_limit
from .getters import get_network, get_delivery, must_be_prod_or_staff

def get_subgroup(u_id, nw_id):
    return m.NetworkSubgroup.objects.filter(
        networkmembership__user_id=u_id,
        networkmembership__valid_until=None,
        networkmembership__is_subgroup_staff=True,
        network_id=nw_id
    ).first()


def edit_delivery_purchases(request, delivery, try_subgroup: bool):
    """
    Allows to change the user purchases for a given delivery.
    Access to either every user or a single subgroup depending on requester's status.
    """
    user = request.user
    dv = get_delivery(delivery)
    try:
        must_be_prod_or_staff(request, dv.network)
        is_staff = True
        if try_subgroup:
            sg = get_subgroup(user.id, dv.network_id)
        else:
            sg = None
    except PermissionDenied:
        is_staff = False
        sg = get_subgroup(user.id, dv.network_id)
        if sg is None:
            raise

    if request.method == 'POST':
        _parse_form(request, dv, sg)
        # subgroup, if any, will be inferred from request user status
        return redirect("view_delivery_purchases_html", delivery=dv.id)
    else:
        vars = {
            'user': user, 'delivery': dv, 'subgroup': sg,
            'can_edit_all_subgroups': is_staff and sg is not None }
        vars.update(csrf(request))
        return render(request,'edit_delivery_purchases.html', vars)


def _parse_form(request, dv, sg):
    """
    Parse responses from purchase editions.
    :param request:
    :return:
    """

    d = request.POST.dict()

    #[(product_id, user_id, quantity)*]
    mods: List[Tuple[int, int, float]] = []

    for name, value in d.items():
        bits = name.split('-')
        if len(bits) == 4 and bits[0] == 'pd' and bits[2] == 'u':
            pd_id = int(bits[1])
            u_id = int(bits[3])
            q = float(value.replace(",", "."))
            mods.append((pd_id, u_id, q))

    if not mods:
        return

    # Check that every user is in that network / subgroup
    user_ids = {u_id for (_, u_id, _) in mods}
    if sg:
        assert sg.network_id == dv.network_id
        authorized_users = {u.id for u in m.User.objects.filter(
            networkmembership__valid_until=None,
            networkmembership__subgroup_id=sg.id,
        )}
    else:
        authorized_users = {u.id for u in m.User.objects.filter(
            networkmembership__valid_until=None,
            networkmembership__network_id=dv.network_id,
        )}

    assert user_ids.issubset(authorized_users)

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

    m.JournalEntry.log(request.user, "Modified user purchases in dv-%d", dv.id)
