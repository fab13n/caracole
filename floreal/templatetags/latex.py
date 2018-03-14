#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re

from django import template


register = template.Library()

_unsafe_tex_chars = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless',
        '>': r'\textgreater',
    }
_unsafe_tex_regex = re.compile('|'.join(re.escape(str(key))
                                        for key in sorted(list(_unsafe_tex_chars.keys()), key=lambda item: - len(item))))

@register.filter
def tex_safe(x):
    """Escape TeX's special characters."""
    return _unsafe_tex_regex.sub(lambda match: _unsafe_tex_chars[match.group()], x)


@register.filter
def price_nocurrency(f):
    euros = int(f)
    cents = int(f * 100) % 100
    if cents:
        return r"%d{\scriptsize ,%02d}" % (euros, cents)
    else:
        return r"%d" % euros

@register.filter
def price(f):
    euros = int(f)
    cents = int(f * 100) % 100
    if cents:
        return r"%d{\scriptsize ,%02d\euro}" % (euros, cents)
    else:
        return r"%d{\scriptsize\euro}" % euros

@register.filter
def qty(f):
    return "%g" % f

@register.filter
def short_unit(u):
    if u != 'kg':
        u = 'pc'
    return r"{\scriptsize %s}" % u

@register.filter
def unit(u):
    if u[0].isdigit():
        return r"$\times$" + tex_safe(u)
    else:
        return tex_safe(u)


