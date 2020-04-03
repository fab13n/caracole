# -*- coding: utf-8 -*-

from floreal import models as m
from collections import defaultdict
from django.template.loader import get_template
from django.http import HttpResponse
from django.core.mail import send_mail
from django.conf import settings

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

def invoice_mail(request, network, payment_date):
    deliveries = m.Delivery.objects.filter(network_id=network, state=m.Delivery.FROZEN)
    r = {} # u -> dv -> [pc+]
    t = {} # (u, dv) -> total
    for dv in deliveries:
        for pd in dv.product_set.all():
            for pc in pd.purchase_set.all():
                u = pc.user
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

    text = [u"Récapitulatif des mails envoyés:"]
    for u, dv_pcs in r.items():
        dest = u.email
        vars = {
            'user': u,
            'payment_date': payment_date,
            'dv_pcs_totals' : [{'dv': dv, 'pcs': pcs, 'total': t[(u, dv)]} for dv, pcs in dv_pcs.items()]
        }
        subject = u"Votre commande Civam pour le " + payment_date
        body = render_text('invoice_mail.txt', vars)
        text.append(u"To:"+dest+u"\nSubject: "+subject+u"\n\n"+body+u"\n\n")
        # print u"Send mail to "+dest+u" about "+subject+u":\n\n"+body
        send_mail(subject, body, settings.EMAIL_HOST_USER, [dest])
    
    return non_html_response(["mails"], "txt", u"\n\n".join(text))

