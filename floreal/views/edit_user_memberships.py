#!/usr/bin/python
# -*- coding: utf-8 -*-

import re

from django.core.context_processors import csrf
from django.http import HttpResponseForbidden
from django.shortcuts import render_to_response, redirect

from .. import models as m


def edit_user_memberships(request, network):
    nw = m.Network.objects.get(id=network)
    if request.user not in nw.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + nw.name)

    if request.method == 'POST':
        if _parse_form(request, nw):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_memberships", network=nw.id)

    # Precompute relationships instead of performing multiple DB queries in each call to `parse_user`
    network_subgroups = nw.subgroup_set.all()
    is_nw_admin = {u.id for u in nw.staff.all()}
    is_sg_admin = {u.id for sg in network_subgroups for u in sg.staff.all()}
    is_sg_user = {u.id:sg.id for sg in network_subgroups for u in sg.users.all()}
    is_nowhere = {u.id for u in m.User.objects.filter(user_of_subgroup=None, is_active=True)}
    is_extra = {sg.extra_user.id for sg in m.Subgroup.objects.all()}

    def parse_user(u):
        return {
            'id': u.id,
            'name': u.first_name + ' ' + u.last_name,
            'email': u.email,
            'subgroup': -2 if u.id in is_nowhere else is_sg_user.get(u.id, -1),
            'is_subgroup_admin': u.id in is_sg_admin,
            'is_network_admin': u.id in is_nw_admin,
            'initial': u.last_name and u.last_name[0].upper() or '?'}

    users = [parse_user(u)
             for u in m.User.objects
                 .filter(is_active=True)
                 .order_by('last_name')
             if u.id not in is_extra]

    vars = {'user': request.user,
            'network': nw,
            'users': users,
            'subgroups':nw.subgroup_set.order_by('name')
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
            if sgid >= 0:
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
