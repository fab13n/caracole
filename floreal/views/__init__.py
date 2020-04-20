#!/usr/bin/python3

from datetime import datetime
import os
import re

from django.shortcuts import render, redirect, reverse
from django.http import HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import html
from django.template.context_processors import csrf
from django.db.models import Count

from caracole import settings
from .. import models as m
from .getters import get_network, get_subgroup, get_delivery, get_candidacy
from .decorators import nw_admin_required, sg_admin_required
from .latex import delivery_table as latex_delivery_table, render_latex
from .spreadsheet import spreadsheet

from .edit_subgroup_purchases import edit_subgroup_purchases
from .edit_user_purchases import edit_user_purchases
from .user_registration import user_register, user_register_post
from .edit_delivery_products import edit_delivery_products
from .edit_user_memberships import edit_user_memberships, json_memberships
from .regulation import adjust_subgroup
from .view_purchases import \
    view_purchases_html, view_purchases_latex, view_purchases_xlsx, view_cards_latex, get_archive, non_html_response
from .candidacies import candidacy, cancel_candidacy, validate_candidacy, leave_network, create_candidacy, manage_candidacies
from .invoice_mail import invoice_mail_form

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
    vars['messages'] = {("Message général", msg.message, msg.id) for msg in m.AdminMessage.objects.filter(everyone=True)}
    vars['messages'] |= {(nw.name, msg.message, msg.id) for nw in user_networks for msg in nw.adminmessage_set.all()}
    vars['messages'] |= {(str(sg), msg.message, msg.id) for sg in user_subgroups for msg in sg.adminmessage_set.all()}
    return render(request,'index.html', vars)


@nw_admin_required()
def network_admin(request, network):
    user = request.user
    nw = get_network(network)
    vars = {'user': user, 'nw': nw,
            'deliveries': m.Delivery.objects.filter(network=nw).exclude(state=m.Delivery.TERMINATED),
            'candidacies': m.Candidacy.objects.filter(subgroup__network=nw),
            'Delivery': m.Delivery}
    return render(request,'network_admin.html', vars)


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
    return render(request,'archived_deliveries.html', vars)


@nw_admin_required()
def delete_archived_delivery(request, delivery):
    dv = get_delivery(delivery)
    if not _dv_has_no_purchase(dv):
        return HttpResponseForbidden('Cette commande n\'est pas vide, passer par l\'admin DB')
    nw = dv.network
    dv.delete()
    m.JournalEntry.log(request.user, "Deleted archived delivery dv-%d (%s) from %s", dv.id, dv.name, nw.name)
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
    m.JournalEntry.log(request.user, "Deleted archived empty deliveries [%s] from %s", ', '.join("dv-%d" % i for i in ids), nw.name)
    return redirect('archived_deliveries', network)


@nw_admin_required()
def create_subgroup(request, network, name):
    # name = urllib.unquote(name)
    nw = get_network(network)
    if nw.subgroup_set.filter(name=name).exists():
        return HttpResponseBadRequest(u"Il y a déjà un sous-groupe de ce nom dans "+nw.name)
    sg = m.Subgroup.objects.create(name=name, network=nw)
    m.JournalEntry.log(request.user, "Created subgroup sg-%d %s in nw-%d %s", sg.id, name, nw.id, nw.name)
    return redirect('edit_user_memberships', network=nw.id)


@login_required()
def create_network(request, nw_name, sg_name):
    user = request.user
    if not user.is_staff:
        return HttpResponseForbidden("Creation de réseaux réservée au staff")
    if m.Network.objects.filter(name__iexact=nw_name).exists():
        return HttpResponseBadRequest("Il y a déjà un réseau nommé "+nw_name)
    nw = m.Network.objects.create(name=nw_name)
    sg = m.Subgroup.objects.create(name=sg_name, network=nw)
    nw.staff.add(user)
    sg.staff.add(user)
    sg.users.add(user)
    target = request.GET.get('next', False)
    m.JournalEntry.log(user, "Created network nw-%d %s with subgroup sg-%d %s", nw.id, nw_name, sg.id, sg_name)
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
    return render(request,'edit_delivery.html', vars)


def list_delivery_models(request, network, all_networks=False):
    """Propose to create a delivery based on a previous delivery."""
    nw = m.Network.objects.get(id=network)
    if all_networks:
        authorized_networks = request.user.staff_of_network.all()
        deliveries = m.Delivery.objects.filter(network__in=authorized_networks)
    else:
        deliveries =  m.Delivery.objects.filter(network=nw)
    vars = {
        'user': request.user,
        'nw': nw,
        'all_networks': all_networks,
        'deliveries': deliveries.order_by("network", "-id")
    }
    return render(request,'list_delivery_models.html', vars)


@nw_admin_required()
def create_delivery(request, network=None, dv_model=None):

    """Create a new delivery, then redirect to its edition page."""
    if network:
        nw = m.Network.objects.get(id=network)
    else:
        nw = dv_model.network
    if dv_model:
        dv_model = m.Delivery.objects.get(id=dv_model)

    if request.user not in nw.staff.all():
        # Vérifier qu'on est bien admin du bon réseau
        return HttpResponseForbidden('Réservé aux administrateurs du réseau ' + nw.name)
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
              'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    now = datetime.now()
    name = '%s %d' % (months[now.month-1], now.year)
    n = 1
    while m.Delivery.objects.filter(network=nw, name=name).exists():
        if n == 1:
            fmt = "%dème de " + name
        n += 1
        name = fmt % n
    new_dv = m.Delivery.objects.create(name=name, network=nw, state=m.Delivery.PREPARATION)
    if dv_model:
        for prev_pd in dv_model.product_set.all():
            new_dv.description = dv_model.description
            new_dv.save()
            m.Product.objects.create(delivery=new_dv, name=prev_pd.name, price=prev_pd.price,
                                     quantity_per_package=prev_pd.quantity_per_package,
                                     unit=prev_pd.unit, quantity_limit=prev_pd.quantity_limit,
                                     unit_weight=prev_pd.unit_weight, quantum=prev_pd.quantum,
                                     description=prev_pd.description)
    m.JournalEntry.log(request.user, "Created new delivery dv-%d %s in nw-%d %s", new_dv.id, name, nw.id, nw.name)
    return redirect(reverse('edit_delivery_products', kwargs={'delivery': new_dv.id})+"?new=true")


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
    m.JournalEntry.log(request.user, "Set delivery dv-%d %s/%s in state %s",
                       dv.id, dv.network.name, dv.name, m.Delivery.STATE_CHOICES[state])
    return redirect('edit_delivery', delivery=dv.id)

@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def set_delivery_name(request, delivery, name):
    """Change a delivery's name."""
    dv = get_delivery(delivery)
    prev_name = dv.name
    dv.name = name
    dv.save()
    m.JournalEntry.log(request.user, "Change delivery dv-%d name in nw-%d %s: %s->%s",
                       dv.id, dv.network.id, dv.network.name, prev_name, name)
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
        return HttpResponseBadRequest("Ce sous-groupe ne participe pas à cette livraison.")
    dv.set_stateForSubgroup(sg, state)
    target = request.GET.get('next', False)
    m.JournalEntry.log(request.user, "In nw-%d %s, set subgroup sg-%d %s in state %s for delivery dv-%d %s",
                       dv.network.id, dv.network.name, sg.id, sg.name, state, dv.id, dv.name)
    return redirect(target) if target else redirect('edit_delivery', delivery=dv.id)


@nw_admin_required()
def view_emails_pdf(request, network):
    nw = get_network(network)
    return latex.emails(nw)

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
        if user not in sg.staff.all() and user not in sg.network.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
    elif network:
        vars['subgroups'] = m.Subgroup.objects.filter(network_id=network)
    else:
        return HttpResponseForbidden("Préciser un réseau ou un sous-groupe")
    return render(request,'emails.html', vars)


@login_required()
def view_phones(request, network=None, subgroup=None):
    user = request.user
    vars = {'user': user, 'subgroups': []}
    if network:
        nw = get_network(network)
        if user not in nw.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
        subgroups = nw.subgroup_set.order_by('name')
    if subgroup:
        sg = get_subgroup(subgroup)
        nw = sg.network
        subgroups = [sg]
        if not network:
            vars['network'] = sg.network
        if user not in sg.staff.all() and user not in nw.staff.all():
            return HttpResponseForbidden("Réservé aux admins")
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
    return render(request,'phones.html', vars)


@login_required()
def view_history(request):
    orders = [(nw, m.Order(request.user, dv))
              for nw in m.Network.objects.all()
              for dv in nw.delivery_set.all()]
    orders = [(nw, od) for (nw, od) in orders if od.price > 0]  # Filter out empty orders
    vars = {'user': request.user, 'orders': orders}
    return render(request,"view_history.html", vars)


JOURNAL_LINKS = {
   'cd': '/admin/floreal/candidacy/%d/',
   'nw': '/nw-%d',
   'u': '/admin/auth/user/%d/',
   'dv': '/dv-%d/staff'
}

@nw_admin_required()
def journal(request):
    journal_link_re = re.compile(r'\b([a-z][a-z]?)-([0-9]+)')
    def add_link_to_actions(m):
         txt, code, n = m.group(0, 1, 2)
         href = JOURNAL_LINKS.get(code) 
         return "<a href='%s'>%s</a>" % (href % int(n), txt) if href else txt 

    days = []
    current_day = None
    for entry in m.JournalEntry.objects.all().order_by("-date")[:1024]:
        today = entry.date.strftime("%x")
        action = journal_link_re.sub(add_link_to_actions, html.escape(entry.action))
        record = {'user': entry.user, 'hour': entry.date.strftime("%XZ"), 'action': action}
        if not current_day or current_day['day'] != today:
            current_day = {'day': today, 'entries': [record]}
            days.append(current_day)
        else:
            current_day['entries'].append(record)
    return render(request,"journal.html", {'user': request.user, 'days': days})


@nw_admin_required()
def all_deliveries(request, network, states):
    nw = get_network(network)
    deliveries = list(m.Delivery.objects.filter(network=nw, state__in=states))
    users = m.User.objects.filter(user_of_subgroup__network=nw)

    # u -> dv -> has_purchased
    users_with_purchases = {u: {dv: False for dv in deliveries} for u in users}

    for dv in deliveries:
        for u in users.filter(purchase__product__delivery=dv).distinct():
            users_with_purchases[u][dv] = True

    # Remove network users with no purchases in any delivery
    users_with_purchases = {
        u: dv_pc
        for u, dv_pc in users_with_purchases.items()
        if any(v for v in dv_pc.values())
    }
            
    # t: List[Tuple[m.User, List[Tuple[m.Delivery, bool]]]]
    t = [(u, [(dv, dv_pc[dv]) for dv in deliveries]) for u, dv_pc in users_with_purchases.items()]
    t.sort(key=lambda x: (x[0].last_name, x[0].first_name))

    return {'states': states, 'network': nw, 'table': t}


def all_deliveries_html(request, network, states):
    ctx = all_deliveries(request, network, states)
    return render(request,"all_deliveries.html", ctx)


def all_deliveries_latex(request, network, states):
    ctx = all_deliveries(request, network, states)
    content = render_latex("all_deliveries.tex", ctx)
    name_bits = [get_network(network).name, "active_deliveries", datetime.now().strftime("%Y-%m-%d")]
    return non_html_response(name_bits, "pdf", content)

def editor(request, target, title='Éditer', template="editor.html", **kwargs):
    ctx = dict(title=title, target=target, **kwargs)
    ctx.update(csrf(request))
    return render(request, template, ctx)

@sg_admin_required()
def set_message(request):
    if request.method == "POST":
        P = request.POST
        d = P['destination'].split('-')
        # TODO: check that user has the admin rights suitable for the destination
        if d[0] == 'everyone':
            dest = {'everyone': True}
        elif d[0] == 'nw':
            dest = {'network_id': int(d[1])}
        elif d[0] == 'sg':
            dest = {'subgroups_id': int(d[1])}
        else:
            assert False
        text = P['editor']
        if text.startswith("<p>"):
            text = text[3:]
        if text.endswith("</p>"):
            text = text[:-4]
        msg = m.AdminMessage.objects.create(message=text, **dest)
        return redirect("index")
    else:
        u = request.user
        options = \
            [('Tout le monde', 'everyone')] + \
            [('Sous-groupe %s'%sg.name, 'sg-%d' % sg.id) \
                for sg in u.staff_of_subgroup \
                .annotate(nsg=Count('network__subgroup')) \
                .filter(nsg__gt=1)] + \
            [('Réseau %s'%nw.name, 'nw-%d' % nw.id) \
                for nw in u.staff_of_network.all()]
        return editor(request,
                  title="Message administrateur",
                  template="set_message.html",
                  target="/set-message",
                  options=options)

@sg_admin_required()
def unset_message(request, id):
    # TODO check that user is allowed for that message
    # To be done in a m.Message method
    m.AdminMessage.objects.get(id=int(id)).delete()
    return redirect("index")
