#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.http import HttpResponseForbidden

from .. import models as m
from .getters import get_network


def nw_admin_required(admin_getter=lambda a: a.get('network', None)):
    """Decorate a view function so that it fails unless the user is a network admin.
    If the function takes a `network` kwarg, then the user must be an admin for that network."""
    def decorator(f):
        def g(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return HttpResponseForbidden('Réservé aux administrateurs')
            if user.is_staff:
                return f(request, *args, **kwargs)
            nw = get_network(admin_getter(kwargs))
            if not m.NetworkMembership.objects.filter(user=user, network=nw, is_staff=True).exists():
                    return HttpResponseForbidden('Réservé aux administrateurs du réseau '+nw.name)
            return f(request, *args, **kwargs)
        return g
    return decorator


def regulator_required(admin_getter=lambda a: a.get('network', None)):
    """Decorate a view function so that it fails unless the user is a subgroup or network admin.
    If the function takes a `subgroup` kwarg, then the user must be an admin for that subgroup
    or its network."""
    def decorator(f):
        def g(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return HttpResponseForbidden('Réservé aux administrateurs')
            nw = get_network(admin_getter(kwargs))
            if nw:
                if not (
                    user.staff_of_network.filter(id=nw.id).exists() or
                    user.regulator_of_network.filter(id=nw.id).exists()):
                    return HttpResponseForbidden('Réservé aux régulateurs du réseau '+sg.network.name+'/'+sg.name)
            else:
                if not (
                    user.staff_of_network.filter().exists() or
                    user.regulator_of_network.filter().exists()):
                    return HttpResponseForbidden('Réservé aux administrateurs de sous-groupe')
            return f(request, *args, **kwargs)
        return g
    return decorator