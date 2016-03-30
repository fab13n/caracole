#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime
import os
import urllib

from django.shortcuts import render_to_response, redirect
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail

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
from .adjust_subgroup import adjust_subgroup
from .view_purchases import \
    view_purchases_html, view_purchases_latex, view_purchases_xlsx, view_cards_latex, get_archive


@login_required()
def index(request):
    """Main page: list deliveries open for ordering as a user, networks for which the user is full admin,
     and orders for which he has subgroup-admin actions to take."""

    user = request.user

    SUBGROUP_ADMIN_STATES = [m.Delivery.ORDERING_ALL, m.Delivery.ORDERING_ADMIN,m.Delivery.REGULATING]

    vars = {'user': request.user, 'Delivery': m.Delivery, 'SubgroupState': m.SubgroupStateForDelivery}
    user_subgroups = m.Subgroup.objects.filter(users__in=[user])
    user_networks = [sg.network for sg in user_subgroups]
    vars['deliveries'] = m.Delivery.objects.filter(network__in=user_networks, state=m.Delivery.ORDERING_ALL)

    vars['network_admin'] = m.Network.objects.filter(staff__in=[user])
    subgroup_admin = m.Subgroup.objects.filter(staff__in=[user])
    subgroup_admin = [{'sg': sg,
                       'dv': sg.network.delivery_set.filter(state__in=SUBGROUP_ADMIN_STATES),
                       'cd': sg.candidacy_set.all()}
                       for sg in subgroup_admin]
    subgroup_admin = [sg_dv_cd for sg_dv_cd in subgroup_admin if sg_dv_cd['dv'].exists() or sg_dv_cd['cd'].exists()]
    vars['subgroup_admin'] = subgroup_admin
    return render_to_response('index.html', vars)


@login_required()
def candidacy(request):
    """Generate a page to choose and request candidacy among the legal ones."""
    user = request.user
    user_of_subgroups = m.Subgroup.objects.filter(users__in=[user])
    candidacies = m.Candidacy.objects.filter(user=user)
    # name, user_of, candidate_to, can_be_candidate_to
    networks = []
    for nw in m.Network.objects.all():
        sg_u = user_of_subgroups.filter(network=nw)
        cd = candidacies.filter(subgroup__network=nw)
        item = {'name': nw.name,
                'user_of': sg_u.first() if sg_u.exists() else None,
                'candidate_to': cd.first() if cd.exists() else None,
                'can_be_candidate_to': nw.subgroup_set.all()}
        if item['user_of']:
            item['can_be_candidate_to'] = item['can_be_candidate_to'].exclude(id=item['user_of'].id)
        if item['candidate_to']:
            item['can_be_candidate_to'] = item['can_be_candidate_to'].exclude(id=item['candidate_to'].user.id)
        networks.append(item)
    print networks
    return render_to_response('candidacy.html', {'user': user, 'networks': networks})


@login_required()
def leave_network(request, network):
    """Leave subgroups of this network, as a user and a subgroup admin (not as a network-admin)."""
    user = request.user
    nw = get_network(network)
    for sg in user.user_of_subgroup.filter(network__id=nw.id):
        sg.users.remove(user.id)
    for sg in user.staff_of_subgroup.filter(network__id=nw.id):
        sg.staff.remove(user.id)

    target = request.REQUEST.get('next', False)
    return redirect(target) if target else redirect('candidacy')


@login_required()
def create_candidacy(request, subgroup):
    """Create the candidacy or act immediately if no validation is needed."""
    user = request.user
    sg = get_subgroup(subgroup)
    if not user.user_of_subgroup.filter(id=sg.id).exists(): # No candidacy for a group you already belong to
        # Remove any pending candidacy for a subgroup of the same network
        conflicting_candidacies = m.Candidacy.objects.filter(user__id=user.id, subgroup__network__id=sg.network.id)
        conflicting_candidacies.delete()
        cd = m.Candidacy.objects.create(user=user, subgroup=sg)
        if auto_validate_candidacy(cd):
            # TODO when should confirmation e-mails be avoided? shouldn't it be up to auto_validate_candidacy to decide?
            validate_candidacy_without_checking(request, candidacy=cd.id, response='Y', send_confirmation_mail=True)

    target = request.REQUEST.get('next', False)
    return redirect(target) if target else redirect('candidacy')


def auto_validate_candidacy(cd):
    """Return True if a candidacy should be automatically granted."""
    if cd.subgroup.network.staff.filter(id=cd.user_id).exists():  # network-admin requests are automatically granted
        return True
    if (cd.subgroup.auto_validate or cd.subgroup.network.auto_validate) and\
            m.Subgroup.objects.filter(users=cd.user).exists():
        # Even if the subgroup is marked as auto-accepting, users who haven't been ever accepted in any subgroup
        # Should be manually accepted, to avoid bogus sign-ups.
        return True
    return False

@login_required()
def cancel_candidacy(request, candidacy):
    """Cancel your own, yet-unapproved candidacy."""
    user = request.user
    cd = get_candidacy(candidacy)
    if user != cd.user:
        return HttpResponseForbidden("Vous ne pouvez annuler que vos propres candidatures.")
    cd.delete()
    target = request.REQUEST.get('next', False)
    return redirect(target) if target else redirect('candidacy')


@sg_admin_required(lambda a: get_candidacy(a['candidacy']).subgroup)
def validate_candidacy(request, candidacy, response):
    return validate_candidacy_without_checking(request, candidacy=candidacy, response=response, send_confirmation_mail=True)


def validate_candidacy_without_checking(request, candidacy, response, send_confirmation_mail):
    """A (legal) candidacy has been answered by an admin.
    Perform corresponding membership changes and notify user through e-mail."""
    cd = get_candidacy(candidacy)
    adm = request.user
    adm = u"%s %s (%s)"  % (adm.first_name, adm.last_name, adm.email)
    mail = [u"Bonjour %s, \n\n" % (cd.user.first_name,)]
    if response == 'Y':
        prev_subgroups = cd.user.user_of_subgroup.filter(network__id=cd.subgroup.network.id)
        if prev_subgroups.exists():
            prev_sg = prev_subgroups.first()  # Normally there's only one
            was_sg_admin = prev_sg.staff.filter(id=cd.user_id).exists()
            prev_sg.users.remove(cd.user)
            if was_sg_admin:
                prev_sg.staff.remove(cd.user)
            mail += u"Votre transfert du sous-groupe %s au sous-groupe %s, " % (prev_sg.name, cd.subgroup.name)
        else:
            mail += u"Votre adhésion au sous-groupe %s, " % (cd.subgroup.name,)
            was_sg_admin = False
        mail += u"au sein du réseau %s, a été acceptée" % (cd.subgroup.network.name,)
        mail += u" par %s. " % (adm,) if adm else u" automatiquement. "
        cd.subgroup.users.add(cd.user)
        is_nw_admin = cd.subgroup.network.staff.filter(id=cd.user_id).exists()
        if was_sg_admin and is_nw_admin:
            cd.subgroup.staff.add(cd.user)
            mail += u"Vous êtes également nommé co-administrateur du sous-groupe %s." % (cd.subgroup.name,)
        mail += "\n\n"
        if cd.subgroup.network.delivery_set.filter(state=m.Delivery.ORDERING_ALL).exists():
            mail += u"Une commande est actuellement en cours, dépêchez vous de vous connecter sur le site pour y participer !"
        else:
            mail += u"Vos responsables de sous-groupe vous préviendront par mail quand une nouvelle commande sera ouverte."
    elif adm:  # Negative response from an admin
        mail += u"Votre demande d'adhésion au sous-groupe %s du réseau %s a été refusée par %s. " \
                u"Si cette décision vous surprend, ou vous semble injustifiée, veuillez entrer en contact par " \
                u"e-mail avec cette personne pour clarifier la situation." % (
            cd.subgroup.name, cd.subgroup.network.name, adm)
    else:  # Automatic refusal. Shouldn't happen in the system's current state.
        mail += u"Votre demande d'adhésion au sous-groupe %s du réseau %s a été refusée automatiquement." \
                u"Si cette décision vous surprend, contactez les administrateurs du réseau: %s" % (
            u", ".join(cd.subgroup.network.staff.all()),)

    mail += u"\n\nCordialement, le robot du site de commande des Circuits Courts Caracole."
    title = u"[caracole] Votre demande d'inscription au circuit court "+cd.subgroup.network.name
    if send_confirmation_mail:
        send_mail(subject=title, message=''.join(mail), from_email=settings.EMAIL_HOST_USER, recipient_list=[cd.user.email],
                  fail_silently=True)
    cd.delete()

    # TODO: sent e-mail confirmation to user

    target = request.REQUEST.get('next', False)
    return redirect(target) if target else redirect('candidacy')


@nw_admin_required()
def network_admin(request, network):
    user = request.user
    nw = get_network(network)
    vars = {'user': user, 'nw': nw, 'deliveries': m.Delivery.objects.filter(network=nw).exclude(state=m.Delivery.TERMINATED)}
    return render_to_response('network_admin.html', vars)

@nw_admin_required()
def archived_deliveries(request, network):
    user = request.user
    nw = get_network(network)
    vars = {'user': user, 'nw': nw, 'deliveries': m.Delivery.objects.filter(network=nw, state=m.Delivery.TERMINATED)}
    return render_to_response('archived_deliveries.html', vars)


@nw_admin_required()
def create_subgroup(request, network, name):
    # name = urllib.unquote(name)
    nw = get_network(network)
    if nw.subgroup_set.filter(name=name).exists():
        return HttpResponseBadRequest("Il y a déjà un sous-groupe de ce nom dans "+nw.name)
    m.Subgroup.objects.create(name=name, network=nw)
    return redirect('edit_user_memberships', network=nw.id)


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
        'CAN_EDIT_PRODUCTS': dv.state != m.Delivery.TERMINATED
    }
    return render_to_response('edit_delivery.html', vars)


@nw_admin_required()
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
    # TODO: save probably not necessary
    # TODO: enable same products as in latest delivery
    return redirect('edit_delivery_products', delivery=d.id)


@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def set_delivery_state(request, delivery, state):
    """Change a delivery's state."""
    dv = get_delivery(delivery)
    if request.user not in dv.network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau '+dv.network.name)
    if state not in m.Delivery.STATE_CHOICES:
        return HttpResponseBadRequest(state+" n'est pas un état valide.")
    must_save = dv.state <= m.Delivery.REGULATING < state
    dv.state = state
    dv.save()
    if must_save:
        save_delivery(dv)
    return redirect('edit_delivery', delivery=dv.id)


def save_delivery(dv):
    """Save an Excel spreadsheet and a PDF table of a delivery that's just been completed."""
    file_name = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.xlsx" % dv.id)
    with open(file_name, 'wb') as f:
        f.write(spreadsheet(dv, dv.network.subgroup_set.all()))
    file_name = os.path.join(settings.DELIVERY_ARCHIVE_DIR, "dv-%d.pdf" % dv.id)
    with open(file_name, 'wb') as f:
        f.write(latex_delivery_table(dv))


@sg_admin_required()
def set_subgroup_state_for_delivery(request, subgroup, delivery, state):
    """Change the state of a subgroup/delivery combo."""
    dv = get_delivery(delivery)
    sg = get_subgroup(subgroup)
    if sg.network != dv.network:
        return HttpResponseBadRequest("Ce sous-groupe ne participe pas à cette livraison.")
    dv.set_stateForSubgroup(sg, state)
    target = request.REQUEST.get('next', False)
    return redirect(target) if target else redirect('edit_delivery', delivery=dv.id)


@login_required()
def view_emails(request, network=None, subgroup=None):
    user = request.user
    vars = {'user': user}
    if network:
        nw = get_network(network)
        vars['network'] = nw
        if user not in nw.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
    if subgroup:
        sg = get_subgroup(subgroup)
        vars['subgroups'] = [sg]
        if not network:
            vars['network'] = sg.network
        if user not in sg.staff.all() and user not in nw.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
    elif network:
        vars['subgroups'] = m.Subgroup.objects.filter(network_id=network)
    else:
        raise Exception("Need network or subgroup")
    return render_to_response('emails.html', vars)


@login_required()
def view_history(request):
    orders = [(nw, m.Order(request.user, dv))
              for nw in m.Network.objects.all()
              for dv in nw.delivery_set.all()]
    orders = [(nw, od) for (nw, od) in orders if od.price > 0]  # Filter out empty orders
    vars = {'user': request.user, 'orders': orders}
    return render_to_response("view_history.html", vars)

