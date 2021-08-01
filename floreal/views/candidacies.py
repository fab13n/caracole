#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.core.mail import send_mail
from django.db.models.functions import Now

from caracole import settings
from .. import models as m
from .getters import get_network, get_user
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
        item = {
            "name": nw.name,
            "id": nw.id,
            "description": nw.description or "",
            "is_member": nw.members.filter(id=user.id).exists(),
            "is_candidate": nw.candidates.filter(id=user.id).exists(),
        }
        networks.append(item)
    return render(request, "candidacy.html", {"user": user, "networks": networks})


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
    """Create the candidacy or act immediately if no validation is needed."""
    user = request.user
    nw = get_network(network)
    if nw.members.filter(id=user.id).exists():
        m.JournalEntry.log(user, "Applied for nw-%d, but was already member", nw.id)
        pass  # already member
    elif (
        nw.auto_validate
        and m.NetworkMembership.objects.filter(user=user, is_candidate=False).exists()
    ):
        # This user has already been accepted somewhere at least once
        m.JournalEntry.log(user, "Applied for nw-%d, automatically granted", nw.id)
        validate_candidacy_without_checking(
            request, network=nw, user=user, response="Y", send_confirmation_mail=True
        )
    else:
        m.NetworkMembership.objects.create(
            network=nw, user=user, is_candidate=True, is_buyer=False
        )
        m.JournalEntry.log(user, "Applied for nw-%d, candidacy pending", nw.id)

    target = request.GET.get("next")
    return redirect(target or "index")


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


@nw_admin_required()
def validate_candidacy(request, network, user, response):
    nw = get_network(network)
    u = get_user(user)
    staff_user = request.user
    if (
        not staff_user.is_staff
        and not m.NetworkMembership.objects.filter(
            network_id=nw.id, user_id=staff_user.id, valid_until=None
        ).exists()
    ):
        return HttpResponseForbidden(
            "Réservé aux administrateurs du réseau " + network.name
        )

    m.JournalEntry.log(
        request.user,
        "Candidacy from u-%d to nw-%d is %s",
        u.id,
        nw.id,
        ("Granted" if response == "Y" else "Rejected"),
    )
    return validate_candidacy_without_checking(
        request, user=u, network=nw, response=response, send_confirmation_mail=True
    )


@nw_admin_required()
def manage_candidacies(request):
    if request.user.is_staff:
        candidacies = m.NetworkMembership.objects.filter(
            is_candidate=True, valid_until=None
        )
    else:
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


def validate_candidacy_without_checking(
    request, network, user, response, send_confirmation_mail
):
    """A (legal) candidacy has been answered by an admin.
    Perform corresponding membership changes and notify user through e-mail."""
    adm = request.user
    adm = "%s %s (%s)" % (adm.first_name, adm.last_name, adm.email)
    mail = ["Bonjour %s, \n\n" % (user.first_name,)]
    nm = m.NetworkMembership.objects.get(
        user=user, network=network, is_candidate=True, valid_until=None
    )
    if response == "Y":
        mail += f"Votre adhésion au réseau {network.name} a été acceptée"
        mail += f" par {adm}. " if adm else " automatiquement. "
        mail += "\n\n"
        if network.delivery_set.filter(state=m.Delivery.ORDERING_ALL).exists():
            mail += "Une commande est actuellement en cours, dépêchez vous de vous connecter sur le site pour y participer !"
        else:
            mail += "Vos responsables de réseau vous préviendront par mail quand une nouvelle commande sera ouverte."
        m.NetworkMembership.objects.create(user=user, network=network, is_buyer=True)
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

    # Terminate candidacy validity
    nm.valid_until = Now()
    nm.save()

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
