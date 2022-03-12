#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.core.mail import send_mail
from django.db.models.functions import Now

from django.conf import settings
from .. import models as m
from .getters import get_network, get_user, must_be_staff


@login_required()
def leave_network(request, network):
    """Leave subgroups of this network, as a user and a subgroup admin (not as a network-admin)."""
    user = request.user
    nw = get_network(network)
    m.JournalEntry.log(user, "Left network nw-%d %s", nw.id, nw.name)
    nw.members.remove(user.id)
    target = request.GET.get("next", False)
    return redirect(target) if target else redirect("index")


@login_required()
def create_candidacy(request, network):
    """Create either the candidacy or the buyer membership, depending on whether validation is needed."""
    user = request.user
    nw = get_network(network)
    # TODO if there are orders and the candicacy ends up granted,
    #      we should jump straight to ordering anchor.
    r = redirect(request.GET.get("next", "index"))
    nm = m.NetworkMembership.objects.filter(
        valid_until=None,
        user=user,
        network=nw   
    ).first()

    if nm is None:
        pass
    elif nm.is_candidate:
        m.JournalEntry.log(user, "Applied for nw-%d, but was already candidate", nw.id)
        return r
    elif nm.is_buyer:
        m.JournalEntry.log(user, "Applied for nw-%d, but was already a buyer", nw.id)
        return r
    elif nm.is_staff:
        m.JournalEntry.log(user, "Staff for nw-%d made themself a buyer", nw.id)
        _validate_candidacy_without_checking(
            request, network=nw, user=user, response="Y", send_confirmation_mail=True
        )
        return r

    # No active membership for this network
    if nw.auto_validate and m.NetworkMembership.objects.filter(user=user, is_candidate=False).exists():
        # This user has already been accepted somewhere at least once
        m.JournalEntry.log(user, "Applied for nw-%d, automatically granted", nw.id)
        _validate_candidacy_without_checking(
            request, network=nw, user=user, response="Y", send_confirmation_mail=True
        )
        return r
    else:
        m.NetworkMembership.objects.create(network=nw, user=user, is_candidate=True, is_buyer=False)
        m.JournalEntry.log(user, "Applied for nw-%d, candidacy pending", nw.id)
        return r


@login_required()
def cancel_candidacy(request, network):
    """Cancel your own, yet-unapproved candidacy."""
    user = request.user
    nw = get_network(network)
    # Mark end of validity
    m.NetworkMembership.objects.filter(
        network=nw, user=user, is_candidate=True, valid_until=None
    ).update(valid_until=Now())
    m.JournalEntry.log(user, "Cancelled own application for nw-%d", nw.id)
    return redirect(request.GET.get(next, "index"))


def validate_candidacy(request, network, user, response):
    nw = get_network(network)
    must_be_staff(request, nw)
    u = get_user(user)

    m.JournalEntry.log(
        request.user,
        "Candidacy from u-%d to nw-%d is %s",
        u.id,
        nw.id,
        ("Granted" if response == "Y" else "Rejected"),
    )
    return _validate_candidacy_without_checking(
        request, user=u, network=nw, response=response, send_confirmation_mail=True
    )


def manage_candidacies(request):
    if request.user.is_staff:
        candidacies = m.NetworkMembership.objects.filter(
            is_candidate=True, valid_until=None
        )
    else:
        # TODO could be merged into a single request
        staff_of_networks = m.Network.objects.filter(
            networkmembership__user=request.user,
            networkmembership__is_staff=True,
            networkmembership__valid_until=None,
        )
        candidacies = m.NetworkMembership.objects.filter(
            is_candidate=True, network__in=staff_of_networks, valid_until=None
        )
    candidacies = candidacies.select_related().order_by(
        "network__name", "user__last_name", "user__first_name"
    )
    return render(
        request,
        "manage_candidacies.html",
        {"user": request.user, "candidacies": candidacies},
    )


def _validate_candidacy_without_checking(
    request, network, user, response, send_confirmation_mail
):
    """A candidacy has been answered by an admin.
    Perform corresponding membership changes and notify user through e-mail."""
    adm = request.user
    adm = "%s %s (%s)" % (adm.first_name, adm.last_name, adm.email)
    mail = ["Bonjour %s, \n\n" % (user.first_name,)]

    # Terminate candidacy validity
    nm = m.NetworkMembership.objects.filter(
        user=user, network=network, is_candidate=True, valid_until=None
    ).first()
    if nm is not None:
        nm.valid_until = Now()
        nm.save()

    if response == "Y":
        mail += f"Votre adhésion au réseau {network.name} a été acceptée"
        mail += f" par {adm}. " if adm else " automatiquement. "
        mail += "\n\n"
        if network.delivery_set.filter(state=m.Delivery.ORDERING_ALL).exists():
            mail += "Une commande est actuellement en cours, dépêchez vous de vous connecter sur le site pour y participer !"
        else:
            mail += "Vos responsables de réseau vous préviendront par mail quand une nouvelle commande sera ouverte."

        # Create membership record if needed; there's a concurrency risk if the same candidacy is granted
        # several times in a row or simultaneously by several people => check for existence before creating.
        m.NetworkMembership.objects.get_or_create(user=user, network=network, is_buyer=True, valid_until=None)

    elif adm:  # Negative response from an admin
        mail += (
            f"Votre demande d'adhésion au réseau {network.name} a été refusée par {adm}. "
            f"Si cette décision vous surprend, ou vous semble injustifiée, veuillez entrer en contact par "
            f"e-mail avec cette personne pour clarifier la situation."
        )
    else:  # Automatic refusal. Shouldn't happen in the system's current state.
        mail += (
            f"Votre demande d'adhésion au réseau {network.name} a été refusée automatiquement."
            "Si cette décision vous surprend, contactez les administrateurs du réseau."
        )

    mail += "\n\nCordialement, le robot du site de commande des Circuits Courts Civam."
    mail += "\n\nLien vers le site : http://solalim.civam-occitanie.fr"
    title = (
        settings.EMAIL_SUBJECT_PREFIX
        + " Votre demande d'inscription au réseau "
        + network.name
    )
    if send_confirmation_mail:
        send_mail(
            subject=title,
            message="".join(mail),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    return redirect(request.GET.get("next", "index"))
