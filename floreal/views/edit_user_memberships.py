#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re

import django
if django.VERSION < (1, 8):
    from django.core.context_processors import csrf
else:
    from django.template.context_processors import csrf
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect

from .. import models as m
from .getters import get_network
from .decorators import nw_admin_required


@nw_admin_required()
def json_memberships(request, network):
    nw = get_network(network)
    # if request.user not in nw.staff.all():
    #    return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + nw.name)

    # Precompute relationships instead of performing multiple DB queries in each call to `parse_user`
    network_subgroups = nw.subgroup_set.all()
    is_nw_admin = {u.id for u in nw.staff.all()}
    is_sg_admin = {u.id for sg in network_subgroups for u in sg.staff.all()}
    is_sg_user = {u.id: sg.id for sg in network_subgroups for u in sg.users.all()}
    is_nowhere = {u.id for u in m.User.objects.filter(user_of_subgroup=None, is_active=True)}
    is_extra = {sg.extra_user.id for sg in m.Subgroup.objects.all()}

    def parse_user(u):
        return {
            'id': u.id,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'subgroup': -2 if u.id in is_nowhere else is_sg_user.get(u.id, -1),
            'is_subgroup_admin': u.id in is_sg_admin,
            'is_network_admin': u.id in is_nw_admin,
            'initial': u.last_name and u.last_name[0].upper() or '?'}

    users = {u.id: parse_user(u)
             for u in m.User.objects
                 .filter(is_active=True)
                 .order_by('last_name')
             if u.id not in is_extra}

    sorted_users = [u['id'] for u in sorted(users.values(), key=lambda u: u['last_name'].lower())]

    vars = {'users': users,
            'sorted_users': sorted_users,
            'subgroups': [{'id': sg.id, 'name': sg.name} for sg in nw.subgroup_set.order_by('name')]
    }
    return JsonResponse(vars)


@nw_admin_required()
def edit_user_memberships(request, network):
    nw = get_network(network)
    if request.user not in nw.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + nw.name)

    if request.method == 'POST':
        if _parse_form(request, nw):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_memberships", network=nw.id)
    vars = {'user': request.user, 'nw': nw, 'multi_sg': nw.subgroup_set.count() > 1}
    vars.update(csrf(request))
    return render(request,'edit_user_memberships.html', vars)


def _parse_form(request, nw):
    d = request.POST
    has_single_subgroup = nw.subgroup_set.count() == 1
    # TODO:
    # in single-subgroup networks, make sure everyone is in the subgroup
    # Do something about people who're subgroup staff but aren't member of the subgroup
    # Do something about people who're in no subgroup. Easy for single-subgroup,
    # Not sure when there are several.
    for uid in re.findall(r'[^u,]+', d['modified']):
        u = m.User.objects.get(pk=int(uid))
        is_network_admin = 'u'+uid+'-network-admin' in d
        was_network_admin = u.staff_of_network.filter(id=nw.id).exists()
        # In single-subgroup networks, network admins are also subgroup admins
        is_subgroup_admin = 'u'+uid+'-subgroup-admin' in d or is_network_admin and has_single_subgroup
        was_subgroup_admin = u.staff_of_subgroup.filter(network=nw).exists()
        sgid = int(d['u'+uid+'-sg'])
        # TODO WTF? Use first(), and don't compare an id with an instance
        old_sg = u.user_of_subgroup.filter(network=nw)
        if not old_sg or old_sg[0] != sgid:  # Subgroup has changed
            for sg in old_sg:
                u.user_of_subgroup.remove(sg)
                u.staff_of_subgroup.remove(sg)
            if sgid >= 0:
                new_sg = m.Subgroup.objects.get(pk=sgid)
                u.user_of_subgroup.add(new_sg)
            else:
                new_sg = None
            if is_subgroup_admin:
                u.staff_of_subgroup.add(new_sg)
            m.JournalEntry.log(request.user, "Moved %s from %s/%s to %s",
                               u.username, nw.name, ('+'.join(sg.name for sg in old_sg) or 'non-member'),
                               (new_sg.name if new_sg else "non-member"))
        else:  # Subgroup hasn't changed
            sg = old_sg[0]
            if was_subgroup_admin and not is_subgroup_admin:
                u.staff_of_subgroup.remove(sg)
            elif not was_subgroup_admin and is_subgroup_admin:
                u.staff_of_subgroup.add(sg)

        if was_network_admin and not is_network_admin:
            m.JournalEntry.log(request.user, "Removed network admin rights for %s in %s", u.username, nw.name)
            u.staff_of_network.remove(nw)
        elif not was_network_admin and is_network_admin:
            m.JournalEntry.log(request.user, "Granted network admin rights for %s in %s", u.username, nw.name)
            u.staff_of_network.add(nw)

        if was_subgroup_admin and not is_subgroup_admin:
            m.JournalEntry.log(request.user, "Removed subgroup admin rights for %s in %s", u.username, nw.name)
        elif not was_subgroup_admin and is_subgroup_admin:
            m.JournalEntry.log(request.user, "Granted subgroup admin rights for %s in %s", u.username, nw.name)

    return True
