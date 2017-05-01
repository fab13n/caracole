#!/usr/bin/python
# -*- coding: utf-8 -*-

from django import template

from floreal import models as m
from floreal import francais

register = template.Library()

@register.filter
def forced_sign(f):
    return u"%+g" % f

@register.filter
def price(f):
    return u"%.02f€" % f


@register.filter
def price_nocurrency(f):
    return u"%.02f" % f

@register.filter
def weight(w):
    if w>=1: return u"%.2gkg" % w
    else: return u"%dg" % (w*1000)

@register.filter
def email(u):
    return '"%s %s" <%s>' % (u.first_name, u.last_name, u.email)


@register.filter
def unit_multiple(unit):
    if unit[0].isdigit():
        return u"×"+unit
    else:
        return u" "+unit


@register.filter
def subgroup_state(sg, dv):
    x = dv.subgroupstatefordelivery_set.filter(delivery=dv, subgroup=sg)
    return x[0].state if x else m.SubgroupStateForDelivery.DEFAULT


@register.filter
def subgroup_has_purchases(sg, dv):
    return m.Purchase.objects.filter(product__delivery_id=dv,
                                     user__in=m.Subgroup.objects.get(pk=sg).users.all()).exists()

@register.filter
def is_admin_of(u, nw_or_sg):
    return nw_or_sg.staff.filter(id=u.id).exists()

@register.filter
def order(dv, u):
    return m.Order(u, dv)

@register.filter
def sort(collection):
    return sorted(collection)

@register.filter
def plural(singular):
    return francais.plural(singular, 2)
