# -*- coding: utf-8 -*-

from floreal import models as m
from collections import defaultdict
from django.template.loader import get_template
from django.http import HttpResponse
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings
from django.shortcuts import redirect, render
from .getters import get_network, get_subgroup, get_candidacy
from django.template.context_processors import csrf
from django.template.base import Template
from django.template.context import Context


def render_text(template_name, ctx):
    t = get_template(template_name)
    text_unicode = t.render(ctx)
    return text_unicode


def non_html_response(name_bits, name_extension, content):
    """Common helper to serve PDF and Excel content."""
    mime_type = "text/plain; charset=utf-8"
    response = HttpResponse(content_type=mime_type)
    response.write(content)
    return response


def invoice_mail_form(request, network):
    nw = get_network(network)
    deliveries = m.Delivery.objects.filter(network_id=network, state=m.Delivery.FROZEN)    
    if request.method == 'POST':
        P = request.POST
        recipients = {u.strip() for u in P['recipients'].split(',')}
        return send_invoice_mail(request, deliveries, recipients, P['subject'], P['body'])
    elif not deliveries:
        return HttpResponse("Acune commande actuellement gelée dans le réseau" + nw.name)
    else:
        vars = {
            'nw': nw,
            'user': request.user,
            'deliveries': deliveries,
            'recipients': m.User.objects.filter(purchase__product__delivery__state=m.Delivery.FROZEN),
            'subject': "Commande "+nw.name,
            'body': get_template('invoice_mail.txt').template.source
        }
        vars.update(csrf(request))
        return render(request, 'invoice_mail_form.html', vars)


def send_invoice_mail(request, deliveries, recipients, subject, body):
    r = {}  # u -> dv -> [pc+]
    t = {}  # (u, dv) -> total
    for dv in deliveries:
        for pd in dv.product_set.all():
            for pc in pd.purchase_set.all():
                u = pc.user
                if u.email not in recipients:
                    continue
                if u not in r:
                    r[u] = {}
                ru = r[u]
                if dv not in ru:
                    ru[dv] = []
                rudv = ru[dv]
                rudv.append(pc)
                k = (u, dv)
                if k not in t:
                    t[k] = 0
                t[k] += pc.price

    datalist = []
    body_template = Template(template_string=body)
    subject_template = Template(template_string=subject)
    for u, dv_pcs in r.items():
        dest = u.email
        ctx = Context({
            'user': u,
            'network': deliveries[0].network,
            'purchases_by_delivery': [{'dv': dv, 'pcs': pcs, 'total': t[(u, dv)]} for dv, pcs in dv_pcs.items()]
        })
        body = body_template.render(ctx)
        subject = subject_template.render(ctx)
        datalist.append((subject, body, settings.EMAIL_HOST_USER, [dest]))

    if True:
        send_mass_mail(datalist, fail_silently=True)
    debug_text = "\n\n=====\n\n".join("To: %s; Subject: %s\n%s" % (
        to, subject, body) for (subject, body, _, [to]) in datalist)

    return non_html_response(["mails"], "txt", text)
