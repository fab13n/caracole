#!/usr/bin/python3
# -*- coding: utf-8 -*-

from numbers import Number

from floreal import models as m
from django.core.exceptions import PermissionDenied
from typing import Union, Optional
from django.db.models import Q


def model_getter(cls):
    def f(x):
        if isinstance(x, str) and x.isdigit() or isinstance(x, Number):
            return cls.objects.get(pk=x)
        elif isinstance(cls, m.IdentifiedBySlug):
            return cls.objects.get(slug__iexact=x)
        else:
            return None
    return f


get_network = model_getter(m.Network)
get_delivery = model_getter(m.Delivery)
get_subgroup = model_getter(m.NetworkSubgroup)
get_user = model_getter(m.User)


def must_be_prod_or_staff(request, network=None):
    u = request.user
    if not u.is_authenticated:
       raise PermissionDenied
    if u.is_staff:
        return "staff"

    if network is None:
        pass
    elif isinstance(network, m.Network):
        pass
    else:
        network = m.Network.objects.get(id=network)

    if network is None:
        raise PermissionDenied  # User is not global staff, per prev test.

    nm = m.NetworkMembership.objects.filter(
        Q(is_staff=True) | Q(is_producer=True),
        user=u,
        valid_until=None,
        network=network
    ).first()

    if nm is not None:
        return "staff" if nm.is_staff else "producer"
    else:
        raise PermissionDenied


def must_be_staff(request, network: Union[m.Network, int, str, None] = None) -> None:
    which = must_be_prod_or_staff(request, network)
    if which != "staff":
        raise PermissionDenied

def must_be_subgroup_staff(request, subgroup: Union[m.NetworkSubgroup, int, str]) -> None:
    u = request.user
    if not u.is_authenticated:
       raise PermissionDenied
    if u.is_staff:
        return "staff"

    sg = get_subgroup(subgroup)
    if not m.NetworkMembership.objects.filter(
        Q(subgroup_id=sg.id, is_subgroup_staff=True) | Q(is_staff=True),
        user=u,
        valid_until=None
        ).exists():
        raise PermissionDenied
