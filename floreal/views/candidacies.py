#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.core.mail import send_mail

from caracole import settings
from .. import models as m
from .getters import get_network
from .decorators import nw_admin_required


@login_required()
def candidacy(request):
    """Generate a page to choose and request candidacy among the legal ones."""
    # TODO Lots of unnecessary SQL queries; subgroups sorted by network should be queried all at once.
    user = request.user
    networks = []
    for nw in m.Network.objects.all():
        # For each network, one can be member, candidate or nothing.
        # If you're candidate you can't be 
        item = {'name': nw.name,
                'id': nw.id,
                'description': nw.description or "",
                'is_member': nw.members.filter(id=user.id).exists(),
                'is_candidate': nw.candidates.filter(id=user.id).exists()
        }
        networks.append(item)
    return render(request, 'candidacy.html', {'user': user, 'networks': networks})


@login_required()
def leave_network(request, network):
    """Leave subgroups of this network, as a user and a subgroup admin (not as a network-admin)."""
    user = request.user
    nw = get_network(network)
    m.JournalEntry.log(user, "Left network nw-%d %s", nw.id, nw.name)
    nw.members.remove(user.id)
    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')


@login_required()
def create_candidacy(request, network):
    """Create the candidacy or act immediately if no validation is needed."""
    user = request.user
    nw = get_network(network)
    if nw.members.filter(id=user.id).exists():
        m.JournalEntry.log(user, "Applied for nw-%d, but was already member", nw.id)
        pass  # already member
    elif nw.auto_validate and user.member_of_network.exists():
        m.JournalEntry.log(user, "Applied for nw-%d, automatically granted", nw.id)
        validate_candidacy_without_checking(request, candidacy=cd.id, response='Y', send_confirmation_mail=True)
    else:
        m.JournalEntry.log(user, "Applied for nw-%d, candidacy pending", nw.id)

    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')

@login_required()
def cancel_candidacy(request, network):
    """Cancel your own, yet-unapproved candidacy."""
    user = request.user
    nw = get_network(network)
    nw.candidates.remove(user)
    m.JournalEntry.log(user, "Cancelled own application for nw-%d", cd.network.id)
    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')


def validate_candidacy(request, candidacy, response):
    try:
        cd = get_candidacy(candidacy)
        u = request.user
        if u not in sg.staff.all() and user not in cd.network.staff.all():
            return HttpResponseForbidden('Réservé aux administrateurs du sous-groupe '+sg.network.name+'/'+sg.name)
    except m.Candidacy.DoesNotExist:
        m.JournalEntry.log("Attempt to treat inexistant candidacy cd-%d from %s", cd.id)
        return redirect(request.GET.get(next, 'candidacy'))

    m.JournalEntry.log(request.user, "%s candidacy cd-%d from u-%d %s to sg-%d %s/%s",
                       ("Granted" if response == 'Y' else 'Rejected'), cd.id, cd.user.id, cd.user.username,
                       cd.subgroup.id, cd.subgroup.network.name, cd.subgroup.name)
    return validate_candidacy_without_checking(request, candidacy=candidacy, response=response, send_confirmation_mail=True)

@nw_admin_required()
def manage_candidacies(request):
    candidacies = m.Candidacy.objects.filter(network__staff__in=[request.user])
    return render(request, 'manage_candidacies.html', {'user': request.user, 'candidacies': candidacies})

def validate_candidacy_without_checking(request, candidacy, response, send_confirmation_mail):
    """A (legal) candidacy has been answered by an admin.
    Perform corresponding membership changes and notify user through e-mail."""
    cd = get_candidacy(candidacy)
    adm = request.user
    adm = "%s %s (%s)" % (adm.first_name, adm.last_name, adm.email)
    mail = ["Bonjour %s, \n\n" % (cd.user.first_name,)]
    if response == 'Y':
        mail += f"Votre adhésion au réseau {cd.network.name} a été acceptée"
        mail += f" par {adm}. " if adm else " automatiquement. "
        cd.network.members.add(cd.user)
        mail += "\n\n"
        if cd.network.delivery_set.filter(state=m.Delivery.ORDERING_ALL).exists():
            mail += "Une commande est actuellement en cours, dépêchez vous de vous connecter sur le site pour y participer !"
        else:
            mail += "Vos responsables de réseau vous préviendront par mail quand une nouvelle commande sera ouverte."
    elif adm:  # Negative response from an admin
        mail += f"Votre demande d'adhésion au réseau {cd.network.name} a été refusée par {adm}. " \
                f"Si cette décision vous surprend, ou vous semble injustifiée, veuillez entrer en contact par " \
                f"e-mail avec cette personne pour clarifier la situation."
    else:  # Automatic refusal. Shouldn't happen in the system's current state.
        mail += f"Votre demande d'adhésion au réseau {cd.network.name} a été refusée automatiquement." \
                "Si cette décision vous surprend, contactez les administrateurs du réseau."

    mail += "\n\nCordialement, le robot du site de commande des Circuits Courts Civam."
    mail += "\n\nLien vers le site : http://solalim.civam-occitanie.fr"
    title = settings.EMAIL_SUBJECT_PREFIX + " Votre demande d'inscription au circuit court "+cd.subgroup.network.name
    if send_confirmation_mail:
        send_mail(subject=title, message=''.join(mail), from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[cd.user.email],
                  fail_silently=True)
    cd.delete()

    target = request.GET.get('next', False)
    return redirect(target) if target else redirect('candidacy')

