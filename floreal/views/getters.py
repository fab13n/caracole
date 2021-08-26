#!/usr/bin/python3
# -*- coding: utf-8 -*-

from numbers import Number

from floreal import models as m


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