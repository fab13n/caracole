#!/usr/bin/python
# -*- coding: utf-8 -*-

import re

from django.core.context_processors import csrf
from django.http import HttpResponseForbidden
from django.shortcuts import render_to_response, redirect

from .. import models as m


def edit_user_memberships(request, network):
    network = m.Network.objects.get(id=network)
    if request.user not in network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + network.name)
    if request.method == 'POST':
        if _parse_form(request, network):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_memberships", network=network.id)

    def parse_user(u):
        r = {'id': u.id, 'name': u.first_name + ' ' + u.last_name}
        try:
            r['subgroup'] = u.user_of_subgroup.get(network=network).id
        except m.Subgroup.DoesNotExist:
            r['subgroup'] = -1
        except m.Subgroup.MultipleObjectsReturned:
            raise ValueError("User %s belong to several subgroups of the same network!" % u.username)
        r['is_subgroup_admin'] = u.staff_of_subgroup.filter(network=network).exists()
        r['is_network_admin'] = network.staff.filter(id=u.id).exists()
        r['initial'] = u.last_name and u.last_name[0].upper() or '?'
        return r
    def is_extra(u):
        return u.user_of_subgroup.filter(extra_user=u).exists()
    users = [parse_user(u) for u in m.User.objects.order_by('last_name') if not is_extra(u)]
    vars = {'user': request.user,
            'network': network,
            'users': users,
            'subgroups':network.subgroup_set.order_by('name')
    }
    vars.update(csrf(request))
    return render_to_response('edit_user_memberships.html', vars)


def _parse_form(request, network):
    d = request.POST
    for uid in re.findall(r'[^u,]+', d['modified']):
        u = m.User.objects.get(pk=int(uid))
        is_network_admin = 'u'+uid+'-network-admin' in d
        was_network_admin = u.staff_of_network.filter(id=network.id).exists()
        is_subgroup_admin = 'u'+uid+'-subgroup-admin' in d
        was_subgroup_admin = u.staff_of_subgroup.filter(network=network).exists()
        sgid = int(d['u'+uid+'-sg'])
        old_sg = u.user_of_subgroup.filter(network=network)
        if not old_sg or old_sg[0] != sgid:
            # Subgroup has changed
            for sg in old_sg:
                u.user_of_subgroup.remove(sg)
                u.staff_of_subgroup.remove(sg)
            if sgid != -1:
                new_sg = m.Subgroup.objects.get(pk=sgid)
                u.user_of_subgroup.add(new_sg)
            if is_subgroup_admin:
                u.staff_of_subgroup.add(new_sg)
        else:  # Subgroup hasn't changed
            sg = old_sg[0]
            if was_subgroup_admin and not is_subgroup_admin:
                u.staff_of_subgroup.remove(sg)
            elif not was_subgroup_admin and is_subgroup_admin:
                u.staff_of_subgroup.add(sg)
        if was_network_admin and not is_network_admin:
            u.staff_of_network.remove(network)
        if not was_network_admin and is_network_admin:
            u.staff_of_network.add(network)
    return True
