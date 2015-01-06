#!/usr/bin/python
# -*- coding: utf8 -*-

from django import template

register = template.Library()

@register.filter
def price(f):
    return u"%.02f€" % f

@register.filter
def price_nocurrency(f):
    return u"%.02f" % f
