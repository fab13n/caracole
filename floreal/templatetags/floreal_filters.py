from datetime import datetime

from django import template
from django.utils.dateparse import parse_date

from floreal import francais
from floreal import models as m

register = template.Library()

@register.filter
def several(x):
    return len(x) > 1

@register.filter
def forced_sign(f):
    return "%+g" % f

@register.filter
def price(f):
    return "%.02f€" % f

@register.filter
def price_nocurrency(f):
    return "%.02f" % f

@register.filter
def weight(w):
    if w>=1: return "%.2gkg" % w
    else: return "%dg" % (w*1000)

@register.filter
def email(u):
    return '"%s %s" <%s>' % (u.first_name, u.last_name, u.email)

@register.filter
def unit_multiple(unit):
    if unit[0].isdigit():
        return "×"+unit
    else:
        return " "+unit

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
def sort(collection):
    return sorted(collection)

@register.filter
def plural(singular):
    return francais.plural(singular, 2)

@register.filter
def days_until(date):
    if isinstance(date, str):
        date = parse_date(date)
    delta = date - datetime.now().date()
    return delta.days

@register.filter
def is_in_the_future(date):
    if date is None:
        return False
    if isinstance(date, str):
        date = parse_date(date)
    return date > datetime.now().date()

