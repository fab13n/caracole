#!/usr/bin/python
# -*- coding: utf-8 -*-

from django import template

register = template.Library()

@register.filter
def price_nocurrency(f):
    euros = int(f)
    cents = int(f * 100) % 100
    if cents:
        return ur"%d{\scriptsize ,%02d}" % (euros, cents)
    else:
        return ur"%d" % euros
@register.filter
def price(f):
    euros = int(f)
    cents = int(f * 100) % 100
    if cents:
        return ur"%d{\scriptsize ,%02d\euro}" % (euros, cents)
    else:
        return ur"%d{\scriptsize\euro}" % euros

@register.filter
def qty(f):
    s = (u"%g" % f).rstrip('0').rstrip('.')
    if len(s) == 0:
        return u"0"
    else:
        return s

@register.filter
def unit(u):
    if u != 'kg':
        u = 'pc'
    return ur"{\scriptsize %s}" % u
