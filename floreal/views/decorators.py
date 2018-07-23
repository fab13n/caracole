#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.http import HttpResponseForbidden

from .. import models as m
from .getters import get_network, get_subgroup


def nw_admin_required(admin_getter=lambda a: a.get('network', None)):
    """Decorate a view function so that it fails unless the user is a network admin.
    If the function takes a `network` kwarg, then the user must be an admin for that network."""
    def decorator(f):
        def g(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated():
                return HttpResponseForbidden('Réservé aux administrateurs')
            nw = get_network(admin_getter(kwargs))
            if nw:
                if user not in nw.staff.all():
                    return HttpResponseForbidden('Réservé aux administrateurs du réseau '+nw.name)
            else:
                if not m.Network.objects.filter(staff__in=[user]).exists():
                    return HttpResponseForbidden('Réservé aux administrateurs de réseau')
            return f(request, *args, **kwargs)
        return g
    return decorator


def sg_admin_required(admin_getter=lambda a: a.get('subgroup', None)):
    """Decorate a view function so that it fails unless the user is a subgroup or network admin.
    If the function takes a `subgroup` kwarg, then the user must be an admin for that subgroup
    or its network."""
    def decorator(f):
        def g(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated():
                return HttpResponseForbidden('Réservé aux administrateurs')
            sg = get_subgroup(admin_getter(kwargs))
            if sg:
                if user not in sg.staff.all() and user not in sg.network.staff.all():
                    return HttpResponseForbidden('Réservé aux administrateurs du sous-groupe '+sg.network.name+'/'+sg.name)
            else:
                if not m.Network.objects.filter(staff__in=[user]).exists() and \
                   not m.Subgroup.objects.filter(staff__in=[user]).exists():
                    return HttpResponseForbidden('Réservé aux administrateurs de sous-groupe')
            return f(request, *args, **kwargs)
        return g
    return decorator