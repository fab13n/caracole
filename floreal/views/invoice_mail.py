# -*- coding: utf-8 -*-

from floreal import models as m
from collections import defaultdict
from django.template.loader import get_template
from django.http import HttpResponse
from django.core.mail import send_mail, send_mass_mail
from django.conf import settings
from django.shortcuts import redirect, render
from .getters import get_network
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
    
    if request.method == "POST":
        P = request.POST
        recipients = {u.strip() for u in P["recipients"].split(",")}
        return send_invoice_mail(
            request, network, recipients, P["subject"], P["body"]
        )
    else:        
        deliveries = m.Delivery.objects.filter(network_id=network, state=m.Delivery.FROZEN)
        if not deliveries:
            return HttpResponse("Aucune commande actuellement gelée dans le réseau" + nw.name)
        vars = {
            "nw": nw,
            "user": request.user,
            "deliveries": deliveries,
            "recipients": m.User.objects.filter(
                purchase__product__delivery__network=nw,
                purchase__product__delivery__state=m.Delivery.FROZEN, 
                is_active=True
            ).distinct(),
            "subject": "Commande " + nw.name,
            "body": get_template("invoice_mail.txt").template.source,
        }
        vars.update(csrf(request))
        return render(request, "invoice_mail_form.html", vars)


def send_invoice_mail(request, network, recipients, subject, body):

    purchases_by_user_and_delivery = {
        u.email: { 
            'user': u, 
            'network': network, 
            'purchases_by_delivery': {}  # dv.id -> {name, purchases, total}
        }
        for u in m.User.objects.filter(email__in=recipients)
    }

    for pc in m.Purchase.objects.filter(
        product__delivery__network=network,
        product__delivery__state=m.Delivery.FROZEN,
    ).select_related("user", "product", "product__delivery", "product__delivery__network"):
        pd = pc.product
        if (ju := purchases_by_user_and_delivery.get(pc.user.email)) is None:
            continue  # User discarded
        purchases_by_delivery = ju['purchases_by_delivery']
        if (jdv := purchases_by_delivery.get(pd.delivery_id)) is None:
            # print("New delivery ", pd.delivery, " for user ", pc.user)
            jdv = purchases_by_delivery[pd.delivery_id] = {
                'name': pd.delivery.name,
                'purchases': [pc],
                'total': pc.price
            }
        else:
            # print("+")
            jdv['purchases'].append(pc)
            jdv['total'] += pc.price

    datalist = []
    body_template = Template(template_string=body)
    subject_template = Template(template_string=subject)

    for item in purchases_by_user_and_delivery.values():
        # Change purchases_by_user_and_delivery[user]['purchases_by_delivery'] from dict to list
        item['purchases_by_delivery'] = list(item['purchases_by_delivery'].values())
        dest = item['user'].email
        ctx = Context(item)
        body = body_template.render(ctx)
        subject = subject_template.render(ctx)
        datalist.append((subject, body, settings.EMAIL_HOST_USER, [dest]))

    if True:
        send_mass_mail(datalist, fail_silently=True)
    text = "\n\n=====\n\n".join(
        "To: %s; Subject: %s\n%s" % (to, subject, body)
        for (subject, body, _, [to]) in datalist
    )

    return non_html_response(["mails"], "txt", text)
