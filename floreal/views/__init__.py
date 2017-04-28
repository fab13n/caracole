#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime
import os

from django.shortcuts import render_to_response, redirect
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required

from caracole import settings
from .. import models as m
from .getters import get_network, get_subgroup, get_delivery, get_candidacy
from .decorators import nw_admin_required, sg_admin_required
from .latex import delivery_table as latex_delivery_table
from .spreadsheet import spreadsheet

from .edit_subgroup_purchases import edit_subgroup_purchases
from .edit_user_purchases import edit_user_purchases
from .user_registration import user_register, user_register_post
from .edit_delivery_products import edit_delivery_products
from .edit_user_memberships import edit_user_memberships, json_memberships
from .regulation import adjust_subgroup
from .view_purchases import \
    view_purchases_html, view_purchases_latex, view_purchases_xlsx, view_cards_latex, get_archive
from .password_reset import password_reset
from .candidacies import candidacy, cancel_candidacy, validate_candidacy, leave_network, create_candidacy

from floreal.views import require_phone_number as phone

@login_required()
def index(request):
    """Main page: list deliveries open for ordering as a user, networks for which the user is full admin,
     and orders for which he has subgroup-admin actions to take."""

    user = request.user

    SUBGROUP_ADMIN_STATES = [m.Delivery.ORDERING_ALL, m.Delivery.ORDERING_ADMIN, m.Delivery.FROZEN, m.Delivery.REGULATING]
    DISPLAYED_STATES = [m.Delivery.ORDERING_ALL, m.Delivery.ORDERING_ADMIN, m.Delivery.FROZEN]

    vars = {'user': request.user, 'Delivery': m.Delivery, 'SubgroupState': m.SubgroupStateForDelivery}
    vars['has_phone'] = phone.has_number(request.user)
    user_subgroups = m.Subgroup.objects.filter(users__in=[user])
    user_networks = [sg.network for sg in user_subgroups]
    vars['deliveries'] = m.Delivery.objects \
        .filter(network__in=user_networks, state__in=DISPLAYED_STATES) \
        .order_by('network', '-id')
    vars['network_admin'] = m.Network.objects.filter(staff__in=[user])
    subgroup_admin = m.Subgroup.objects.filter(staff__in=[user])
    subgroup_admin = [{'sg': sg,
                       'dv': sg.network.delivery_set.filter(state__in=SUBGROUP_ADMIN_STATES),
                       'cd': sg.candidacy_set.all()}
                       for sg in subgroup_admin]
    subgroup_admin = [sg_dv_cd for sg_dv_cd in subgroup_admin if sg_dv_cd['dv'].exists() or sg_dv_cd['cd'].exists()]
    vars['subgroup_admin'] = subgroup_admin
    return render_to_response('index.html', vars)



@nw_admin_required()
def network_admin(request, network):
    user = request.user
    nw = get_network(network)
    vars = {'user': user, 'nw': nw,
            'deliveries': m.Delivery.objects.filter(network=nw).exclude(state=m.Delivery.TERMINATED),
            'candidacies': m.Candidacy.objects.filter(subgroup__network=nw),
            'Delivery': m.Delivery}
    return render_to_response('network_admin.html', vars)


def _dv_has_no_purchase(dv):
    for pd  in dv.product_set.all():
        if pd.purchase_set.exists():
            return False
    return True

@nw_admin_required()
def archived_deliveries(request, network):
    user = request.user
    nw = get_network(network)
    vars = {'user': user, 'nw': nw}
    vars['deliveries'] = m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)
    vars['empty_deliveries'] = [dv for dv in vars['deliveries'] if _dv_has_no_purchase(dv)]
    return render_to_response('archived_deliveries.html', vars)


@nw_admin_required()
def delete_archived_delivery(request, delivery):
    dv = get_delivery(delivery)
    if not _dv_has_no_purchase(dv):
        return HttpResponseForbidden(u'Cette commande n\'est pas vide, passer par l\'admin DB')
    nw = dv.network
    dv.delete()
    m.JournalEntry.log(request.user, "Deleted archived delivery %d (%s) from %s", dv.id, dv.name, nw.name)
    return redirect('archived_deliveries', nw.id)


@nw_admin_required()
def delete_all_archived_deliveries(request, network):
    nw = get_network(network)
    deliveries = m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)
    ids = []  # For loggin purposes
    for dv in deliveries:
        if _dv_has_no_purchase(dv):
            ids.append(dv.id)
            dv.delete()
    m.JournalEntry.log(request.user, "Deleted archived empty deliveries [%s] from %s", ', '.join(str(i) for i in ids), nw.name)
    return redirect('archived_deliveries', network)


@nw_admin_required()
def create_subgroup(request, network, name):
    # name = urllib.unquote(name)
    nw = get_network(network)
    if nw.subgroup_set.filter(name=name).exists():
        return HttpResponseBadRequest(u"Il y a déjà un sous-groupe de ce nom dans "+nw.name)
    m.Subgroup.objects.create(name=name, network=nw)
    m.JournalEntry.log(request.user, "Created subgroup %s in %s", name, nw.name)
    return redirect('edit_user_memberships', network=nw.id)


@login_required()
def create_network(request, nw_name, sg_name):
    user = request.user
    if not user.is_staff:
        return HttpResponseForbidden(u"Creation de réseaux réservée au staff")
    if m.Network.objects.filter(name__iexact=nw_name).exists():
        return HttpResponseBadRequest(u"Il y a déjà un réseau nommé "+nw_name)
    nw = m.Network.objects.create(name=nw_name)
    sg = m.Subgroup.objects.create(name=sg_name, network=nw)
    nw.staff.add(user)
    sg.staff.add(user)
    sg.users.add(user)
    target = request.REQUEST.get('next', False)
    m.JournalEntry.log(user, "Created network %s with subgroup %s", nw_name, sg_name)
    return redirect(target) if target else redirect('network_admin', network=nw.id)


@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def edit_delivery(request, delivery):
    """Edit a delivery as a full network admin: act upon its lifecycle, control which subgroups have been validated,
    change the products characteristics, change other users' orders."""
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
        'Delivery': m.Delivery,
        'SubgroupState': m.SubgroupStateForDelivery,
        'steps': [{'s': s, 'text': m.Delivery.STATE_CHOICES[s], 'is_done': dv.state>=s, 'is_current': dv.state==s} for s in 'ABCDEF'],
        'CAN_EDIT_PURCHASES': dv.state in [m.Delivery.ORDERING_ALL, m.Delivery.ORDERING_ADMIN, m.Delivery.REGULATING],
        'CAN_EDIT_PRODUCTS': dv.state != m.Delivery.TERMINATED,
        'multi_sg': dv.network.subgroup_set.count() > 1
    }
    return render_to_response('edit_delivery.html', vars)


def list_delivery_models(request, network):
    """Propose to create a delivery based on a previous delivery."""
    nw = m.Network.objects.get(id=network)
    vars = {
        'user': request.user,
        'nw': nw,
        'deliveries': m.Delivery.objects.filter(network=nw).order_by("-id")
    }
    return render_to_response('list_delivery_models.html', vars)


@nw_admin_required()
def create_delivery(request, network=None, dv_model=None):

    """Create a new delivery, then redirect to its edition page."""
    if network:
        nw = m.Network.objects.get(id=network)
    elif dv_model:
        dv_model = m.Delivery.objects.get(id=dv_model)
        nw = dv_model.network

    if request.user not in nw.staff.all():
        # Vérifier qu'on est bien admin du bon réseau
        return HttpResponseForbidden(u'Réservé aux administrateurs du réseau ' + nw.name)
    months = [u'Janvier', u'Février', u'Mars', u'Avril', u'Mai', u'Juin', u'Juillet',
              u'Août', u'Septembre', u'Octobre', u'Novembre', u'Décembre']
    now = datetime.now()
    name = '%s %d' % (months[now.month-1], now.year)
    n = 1
    while m.Delivery.objects.filter(network=nw, name=name).exists():
        if n == 1:
            fmt = u"%dème de " + name
        n += 1
        name = fmt % n
    new_dv = m.Delivery.objects.create(name=name, network=nw, state=m.Delivery.PREPARATION)
    if dv_model:
        for prev_pd in dv_model.product_set.all():
            m.Product.objects.create(delivery=new_dv, name=prev_pd.name, price=prev_pd.price,
                                     quantity_per_package=prev_pd.quantity_per_package,
                                     unit=prev_pd.unit, quantity_limit=prev_pd.quantity_limit,
                                     unit_weight=prev_pd.unit_weight, quantum=prev_pd.quantum)
    m.JournalEntry.log(request.user, "Created new delivery %s in %s", name, nw.name)
    return redirect('edit_delivery_products', delivery=new_dv.id)


@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def set_delivery_state(request, delivery, state):
    """Change a delivery's state."""
    dv = get_delivery(delivery)
    if request.user not in dv.network.staff.all():
        return HttpResponseForbidden(u'Réservé aux administrateurs du réseau '+dv.network.name)
    if state not in m.Delivery.STATE_CHOICES:
        return HttpResponseBadRequest(state+u" n'est pas un état valide.")
    must_save = dv.state <= m.Delivery.REGULATING < state
    dv.state = state
    dv.save()
    if must_save:
        save_delivery(dv)
    m.JournalEntry.log(request.user, "Set delivery %s/%s in state %s",
                       dv.network.name, dv.name, m.Delivery.STATE_CHOICES[state])
    return redirect('edit_delivery', delivery=dv.id)

@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def set_delivery_name(request, delivery, name):
    """Change a delivery's name."""
    dv = get_delivery(delivery)
    prev_name = dv.name
    dv.name = name
    dv.save()
    m.JournalEntry.log(request.user, "Change delivery name in %s: %s->%s",
                       dv.network.name, prev_name, name)
    return HttpResponse("")

def save_delivery(dv):
    """Save an Excel spreadsheet and a PDF table of a delivery that's just been completed."""
    file_name_xlsx = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.xlsx" % dv.id)
    with open(file_name_xlsx, 'wb') as f:
        f.write(spreadsheet(dv, dv.network.subgroup_set.all()))
    file_name_pdf = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.pdf" % dv.id)
    with open(file_name_pdf, 'wb') as f:
        f.write(latex_delivery_table(dv))


@sg_admin_required()
def set_subgroup_state_for_delivery(request, subgroup, delivery, state):
    """Change the state of a subgroup/delivery combo."""
    dv = get_delivery(delivery)
    sg = get_subgroup(subgroup)
    if sg.network != dv.network:
        return HttpResponseBadRequest(u"Ce sous-groupe ne participe pas à cette livraison.")
    dv.set_stateForSubgroup(sg, state)
    target = request.REQUEST.get('next', False)
    m.JournalEntry.log(request.user, "In %s, set subgroup %s in state %s for delivery %s",
                       dv.network.name, sg.name, state, dv.name)
    return redirect(target) if target else redirect('edit_delivery', delivery=dv.id)


@login_required()
def view_emails(request, network=None, subgroup=None):
    user = request.user
    vars = {'user': user}
    if network:
        nw = get_network(network)
        vars['network'] = nw
        if user not in nw.staff.all():
            return HttpResponseForbidden(u"Réservé aux admins")
    if subgroup:
        sg = get_subgroup(subgroup)
        vars['subgroups'] = [sg]
        if not network:
            vars['network'] = sg.network
        if user not in sg.staff.all() and user not in sg.network.staff.all():
            return HttpResponseForbidden(u"Réservé aux admins")
    elif network:
        vars['subgroups'] = m.Subgroup.objects.filter(network_id=network)
    else:
        return HttpResponseForbidden(u"Préciser un réseau ou un sous-groupe")
    return render_to_response('emails.html', vars)


@login_required()
def view_phones(request, network=None, subgroup=None):
    user = request.user
    vars = {'user': user, 'subgroups': []}
    if network:
        nw = get_network(network)
        if user not in nw.staff.all():
            return HttpResponseForbidden(u"Réservé aux admins")
        subgroups = nw.subgroup_set.order_by('name')
    if subgroup:
        sg = get_subgroup(subgroup)
        nw = sg.network
        subgroups = [sg]
        if not network:
            vars['network'] = sg.network
        if user not in sg.staff.all() and user not in nw.staff.all():
            return HttpResponseForbidden(u"Réservé aux admins")
    vars['nw'] = nw
    vars['nw_admin'] = nw.staff.order_by('last_name', 'first_name')
    nw_staff_id = set(u.id for u in vars['nw_admin'])
    for sg in subgroups:
        rec = {'sg': sg}
        rec['sg_admin'] = sg.staff.exclude(id__in=nw_staff_id).order_by('last_name', 'first_name')
        sg_staff_id = set(u.id for u in rec['sg_admin']) | nw_staff_id
        rec['sg_user'] = sg.users.exclude(id__in=sg_staff_id).exclude(id=sg.extra_user.id).order_by('last_name', 'first_name')
        vars['subgroups'].append(rec)
    vars['subgroups'].sort(key=lambda rec: rec['sg'].name)
    return render_to_response('phones.html', vars)


@login_required()
def view_history(request):
    orders = [(nw, m.Order(request.user, dv))
              for nw in m.Network.objects.all()
              for dv in nw.delivery_set.all()]
    orders = [(nw, od) for (nw, od) in orders if od.price > 0]  # Filter out empty orders
    vars = {'user': request.user, 'orders': orders}
    return render_to_response("view_history.html", vars)


@nw_admin_required()
def journal(request):
    days = []
    current_day = None
    for entry in m.JournalEntry.objects.all().order_by("-date")[:1024]:
        today = entry.date.strftime("%x")
        record = {'user': entry.user, 'hour': entry.date.strftime("%X"), 'action': entry.action}
        if not current_day or current_day['day'] != today:
            current_day = {'day': today, 'entries': [record]}
            days.append(current_day)
        else:
            current_day['entries'].append(record)
    return render_to_response("journal.html", {'user': request.user, 'days': days})
