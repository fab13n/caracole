#!/usr/bin/python
# -*- coding: utf-8 -*-

from django import template

register = template.Library()

@register.filter
def price(f):
    return u"%.02f€" % f

@register.filter
def price_nocurrency(f):
    return u"%.02f" % f

@register.filter
def email(u):
    return '"%s %s" <%s>' % (u.first_name, u.last_name, u.email)

@register.filter
def unit_multiple(unit):
    if unit[0].isdigit():
        return u"×"+unit
    else:
        return u" "+unit
