#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.core.mail import send_mail

from caracole import settings
from .. import models as m
from .getters import get_network, get_subgroup, get_candidacy
from .decorators import sg_admin_required, nw_admin_required


@login_required()
def candidacy(request):
    """Generate a page to choose and request candidacy among the legal ones."""
    # TODO Lots of unnecessary SQL queries; subgroups sorted by network should be queried all at once.
    user = request.user
    user_of_subgroups = m.Subgroup.objects.filter(users__in=[user])
    candidacies = m.Candidacy.objects.filter(user=user)
    # name, user_of, candidate_to, can_be_candidate_to
    networks = []
    for nw in m.Network.objects.all():
        sg_u = user_of_subgroups.filter(network=nw).first()
        cd = candidacies.filter(subgroup__network=nw).first()
        item = {'name': nw.name,
                'description': nw.description or "",
                'user_of': sg_u,
                'candidate_to': cd,
                'can_be_candidate_to': nw.subgroup_set.all(),
                'has_single_subgroup': nw.subgroup_set.all().count() == 1
        }
        if item['user_of']:
            item['can_be_candidate_to'] = item['can_be_candidate_to'].exclude(id=item['user_of'].id)
        if item['candidate_to']:
            item['can_be_candidate_to'] = item['can_be_candidate_to'].exclude(id=item['candidate_to'].user.id)
        networks.append(item)
    return render(request, 'candidacy.html', {'user': user, 'networks': networks})


@login_required()
def leave_network(request, network):
    """Leave subgroups of this network, as a user and a subgroup admin (not as a network-admin)."""
    user = request.user
    nw = get_network(network)
    m.JournalEntry.log(user, "Left network nw-%d %s", nw.id, nw.name)
    for sg in user.user_of_subgroup.filter(network__id=nw.id):
        sg.users.remove(user.id)
    for sg in user.staff_of_subgroup.filter(network__id=nw.id):
        sg.staff.remove(user.id)

    target = request.GET.get('next', False)
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
            m.JournalEntry.log(user, "Applied for sg-%d %s/%s, automatically granted", sg.id, sg.network.name, sg.name)
            validate_candidacy_without_checking(request, candidacy=cd.id, response='Y', send_confirmation_mail=True)
        else:
            m.JournalEntry.log(user, "Applied for nw-%d sg-%d %s/%s, candidacy pending", sg.network.id, sg.id, sg.network.name, sg.name)
    else:
        m.JournalEntry.log(user, "Applied for sg-%d %s/%s, but was already a member", sg.id, sg.network.name, sg.name)

    target = request.GET.get('next', False)
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
        return HttpResponseForbidden(u"Vous ne pouvez annuler que vos propres candidatures.")
    m.JournalEntry.log(user, "Cancelled own application for sg-%d %s/%s", cd.subgroup.id, cd.subgroup.network.name, cd.subgroup.name)
    cd.delete()
    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')


# Regular checker fails on candidacies handled more than once.
# @sg_admin_required(lambda a: get_candidacy(a['candidacy']).subgroup)
def validate_candidacy(request, candidacy, response):
    try:
        cd = get_candidacy(candidacy)
        sg = cd.subgroup
        u = request.user
        if u not in sg.sg.staff.all() and user not in sg.network.staff.all():
            return HttpResponseForbidden('Réservé aux administrateurs du sous-groupe '+sg.network.name+'/'+sg.name)
    except m.Candidacy.DoesNotExist:
        m.JournalEntry.log("Attempt to treat inexistant candidacy cd-%d from %s", cd.id, cd.user.username)
        return redirect(request.GET.get(next, 'candidacy'))

    m.JournalEntry.log(request.user, "%s candidacy cd-%d from u-%d %s to sg-%d %s/%s",
                       ("Granted" if response == 'Y' else 'Rejected'), cd.id, cd.user.id, cd.user.username,
                       cd.subgroup.id, cd.subgroup.network.name, cd.subgroup.name)
    return validate_candidacy_without_checking(request, candidacy=candidacy, response=response, send_confirmation_mail=True)

@nw_admin_required()
def manage_candidacies(request, network):
    nw = get_network(network)
    candidacies = m.Candidacy.objects.filter(subgroup__network=nw)
    return render(request, 'manage_candidacies.html', {'user': request.user, 'nw': nw, 'candidacies': candidacies})

def validate_candidacy_without_checking(request, candidacy, response, send_confirmation_mail):
    """A (legal) candidacy has been answered by an admin.
    Perform corresponding membership changes and notify user through e-mail."""
    cd = get_candidacy(candidacy)
    adm = request.user
    adm = "%s %s (%s)" % (adm.first_name, adm.last_name, adm.email)
    mail = ["Bonjour %s, \n\n" % (cd.user.first_name,)]
    if response == 'Y':
        prev_subgroups = cd.user.user_of_subgroup.filter(network__id=cd.subgroup.network.id)
        if prev_subgroups.exists():
            prev_sg = prev_subgroups.first()  # Normally there's only one
            was_sg_admin = prev_sg.staff.filter(id=cd.user_id).exists()
            prev_sg.users.remove(cd.user)
            if was_sg_admin:
                prev_sg.staff.remove(cd.user)
            mail += "Votre transfert du sous-groupe %s au sous-groupe %s, " % (prev_sg.name, cd.subgroup.name)
        else:
            mail += "Votre adhésion au sous-groupe %s, " % (cd.subgroup.name,)
            was_sg_admin = False
        mail += "au sein du réseau %s, a été acceptée" % (cd.subgroup.network.name,)
        mail += " par %s. " % (adm,) if adm else " automatiquement. "
        cd.subgroup.users.add(cd.user)
        is_nw_admin = cd.subgroup.network.staff.filter(id=cd.user_id).exists()
        if was_sg_admin and is_nw_admin:
            cd.subgroup.staff.add(cd.user)
            mail += "Vous êtes également nommé co-administrateur du sous-groupe %s." % (cd.subgroup.name,)
        mail += "\n\n"
        if cd.subgroup.network.delivery_set.filter(state=m.Delivery.ORDERING_ALL).exists():
            mail += "Une commande est actuellement en cours, dépêchez vous de vous connecter sur le site pour y participer !"
        else:
            mail += "Vos responsables de sous-groupe vous préviendront par mail quand une nouvelle commande sera ouverte."
    elif adm:  # Negative response from an admin
        mail += "Votre demande d'adhésion au sous-groupe %s du réseau %s a été refusée par %s. " \
                "Si cette décision vous surprend, ou vous semble injustifiée, veuillez entrer en contact par " \
                "e-mail avec cette personne pour clarifier la situation." % (
            cd.subgroup.name, cd.subgroup.network.name, adm)
    else:  # Automatic refusal. Shouldn't happen in the system's current state.
        mail += "Votre demande d'adhésion au sous-groupe %s du réseau %s a été refusée automatiquement." \
                "Si cette décision vous surprend, contactez les administrateurs du réseau: %s" % (
            cd.subgroup.name, cd.subgroup.network.name,
            ", ".join(cd.subgroup.network.staff.all()),)

    mail += "\n\nCordialement, le robot du site de commande des Circuits Courts Civam."
    mail += "\n\nLien vers le site : http://solalim.civam-occitanie.fr"
    title = settings.EMAIL_SUBJECT_PREFIX + " Votre demande d'inscription au circuit court "+cd.subgroup.network.name
    if send_confirmation_mail:
        send_mail(subject=title, message=''.join(mail), from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[cd.user.email],
                  fail_silently=True)
    cd.delete()

    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')

