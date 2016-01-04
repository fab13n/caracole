#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime

from django.shortcuts import render_to_response, redirect
from django.core.urlresolvers import reverse
import django.contrib.auth.views as auth_view
from django.http import HttpResponseForbidden

from .. import models as m
from .edit_subgroup_purchases import edit_subgroup_purchases
from .edit_user_purchases import edit_user_purchases
from .user_registration import user_register, user_register_post
from .edit_delivery_products import edit_delivery_products
from .edit_user_memberships import edit_user_memberships
from .adjust_subgroup import adjust_subgroup
from .view_purchases import \
    view_purchases_html, view_purchases_pdf, view_purchases_latex, view_purchases_xlsx, view_cards_latex


def index(request):
    """Main page: sum-up of current deliveries, links to active pages."""
    user = request.user

    if not user.is_authenticated():
        return redirect(reverse(auth_view.login), args={'redirect_field_name': 'toto'})

    user_subgroups = m.Subgroup.objects.filter(users__in=[user])
    user_networks = [sg.network for sg in user_subgroups]

    nw2staff_of = {}  # network -> subgroup I'm member of
    nw2user_of = {}   # network -> subgroup I'm staffing
    for nw in user_networks:
        for sg in nw.subgroup_set.all():
            if user in sg.staff.all():
                nw2staff_of[nw] = sg
            if user in sg.users.all():
                nw2user_of[nw] = sg

    def subgroup_state(dv, sg):
        return dv.state == 'C' and dv.get_stateForSubgroup(sg)

    vars = {'user': user,
            'networks': [{'network': nw,
                          'subgroup': nw2user_of[nw],
                          'staffed_subgroup': nw2staff_of.get(nw, False),
                          'is_network_staff': user in nw.staff.all(),
                          'deliveries': [{'delivery': dv,
                                          'order': m.Order(user, dv),
                                          'subgroup_state': subgroup_state(dv, nw2user_of[nw])
                                          } for dv in nw.delivery_set.all()],
                          } for nw in user_networks]
            }
    return render_to_response('index.html', vars)


def edit_delivery(request, delivery):
    dv = m.Delivery.objects.get(id=delivery)
    if dv.network.staff.filter(id=request.user.id).exists():
        # All subgroups in the network for network admins
        subgroups = dv.network.subgroup_set.all()
    else:
        # Only subgroups in which user in subgroup-admin
        subgroups = dv.network.subgroup_set.filter(staff=request.user)
    vars = {
        'user': request.user,
        'dv': dv,
        'subgroups': subgroups,
        'S': m.Delivery.STATE_CHOICES,
        'CAN_VIEW_NETWORK': 1,  # always true for admins
        'CAN_EDIT_PURCHASES': 1,  # state != frozen
        'CAN_EDIT_PRODUCTS': 1,  # is network admin
    }
    return render_to_response('delivery-admin/edit.html', vars)


def create_delivery(request, network):
    """Create a new delivery, then redirect to its edition page."""
    network = m.Network.objects.get(id=network)
    if request.user not in network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau '+network.name)
    months = [u'Janvier', u'Février', u'Mars', u'Avril', u'Mai', u'Juin', u'Juillet',
              u'Août', u'Septembre', u'Octobre', u'Novembre', u'Décembre']
    now = datetime.now()
    name = '%s %d' % (months[now.month-1], now.year)
    n = 1
    while m.Delivery.objects.filter(network=network, name=name).exists():
        if n == 1:
            fmt = u"%dème de " + name
        n += 1
        name = fmt % n
    d = m.Delivery.objects.create(network=network, name=name, state=m.Delivery.PREPARATION)
    d.save()
    return redirect('edit_delivery_products', delivery=d.id)


def set_delivery_state(request, delivery, state):
    """Change a delivery's state between "Open", "Closed" and "Delivered"."""
    delivery = m.Delivery.objects.get(id=delivery)
    if request.user not in delivery.network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau '+delivery.network.name)
    [state_code] = [code for (code, name) in m.Delivery.STATE_CHOICES.items() if name == state]
    delivery.state = state_code
    delivery.save()
    return redirect('index')

def set_subgroup_state_for_delivery(request):
    """Change the delivery state for this subgroup."""
    delivery = m.Delivery.objects.get(id=request.POST.get('dv'))
    subgroup = m.Subgroup.objects.get(id=request.POST.get('sg'))
    state = int(request.POST.get('state'))
    delivery.set_stateForSubgroup(subgroup, state)
    return redirect('index')


def view_emails(request, network=None, subgroup=None):
    # TODO: protect from unwarranted access
    vars = {'user': request.user}
    if network:
        vars['network'] = m.Network.objects.get(id=int(network))
    if subgroup:
        sg = m.Subgroup.objects.get(id=subgroup)
        vars['subgroups'] = [sg]
        if not network:
            vars['network'] = sg.network
    elif network:
        vars['subgroups'] = m.Subgroup.objects.filter(network_id=network)
    else:
        raise Exception("Need network or subgroup")
    return render_to_response('emails.html', vars)


def view_history(request, network):
    network = m.Network.objects.get(id=network)
    vars = {'user': request.user, 'orders': [m.Order(request.user, dv) for dv in network.delivery_set.all()]}
    return render_to_response("view_history.html", vars)
