#!/usr/bin/python
# -*- coding: utf-8 -*-

from numbers import Number

from floreal import models as m


def model_getter(cls, field_names=None):
    def f(x):
        if isinstance(x, basestring) and x.isdigit() or isinstance(x, Number):
            return cls.objects.get(pk=x)
        elif isinstance(x, cls):
            return x
        elif field_names and isinstance(x, basestring):
            field_vals = x.split(":")
            kwargs = { k+"__iexact": v.replace('+', ' ') for k, v in zip(field_names, field_vals)}
            return cls.objects.get(**kwargs)
        else:
            return None
    return f


get_network = model_getter(m.Network, ['name'])
get_subgroup = model_getter(m.Subgroup, ['network__name', 'name'])
get_delivery = model_getter(m.Delivery, ['network__name', 'name'])
get_candidacy = model_getter(m.Candidacy)

