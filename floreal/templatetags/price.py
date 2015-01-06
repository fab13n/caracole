#!/usr/bin/python
# -*- coding: utf8 -*-

from django import template

register = template.Library()

@register.filter
def price(f):
    return u"%.02f€" % f
