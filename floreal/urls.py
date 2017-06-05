#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

#from django_markdown import urls as django_markdown_urls

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),

    url(r'^new-nw/(?P<nw_name>[^./]+)/(?P<sg_name>[^./]+)$', views.create_network, name='create_network'),
    url(r'^new-dv/nw-(?P<network>[^./]+)/list$', views.list_delivery_models, name='list_delivery_models'),
    url(r'^new-dv/dv-(?P<dv_model>[^./]+)$', views.create_delivery, name='create_delivery_copy'),
    url(r'^new-dv/nw-(?P<network>[^./]+)$', views.create_delivery, kwargs={'dv_model': None}, name='create_empty_delivery'),
    url(r'^new-sg/nw-(?P<network>[^./]+)/(?P<name>.+)$', views.create_subgroup, name='create_subgroup'),

    url(r'^nw-(?P<network>[^./]+)$', views.network_admin, name='network_admin'),
    url(r'^nw-(?P<network>[^./]+)/archives$', views.archived_deliveries, name='archived_deliveries'),
    url(r'^nw-(?P<network>[^./]+)/edit-users$', views.edit_user_memberships, name='edit_user_memberships'),
    url(r'^nw-(?P<network>[^./]+)/edit-users.json$', views.json_memberships, name='json_memberships'),
    url(r'^nw-(?P<network>[^./]+)/all-deliveries/(?P<states>[A-Z]+)$', views.all_deliveries, name='all_deliveries'),

    url(r'^dv-(?P<delivery>[^./]+)$', views.edit_user_purchases, name='edit_user_purchases'),
    url(r'^dv-(?P<delivery>[^./]+)/staff$', views.edit_delivery, name='edit_delivery'),
    url(r'^dv-(?P<delivery>[^./]+)/edit-products$', views.edit_delivery_products, name='edit_delivery_products'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/edit$',
        views.edit_subgroup_purchases, name='edit_subgroup_purchases'),
    url(r'^dv-(?P<delivery>[^./]+)/set-state/(?P<state>[A-Za-z]+)$', views.set_delivery_state, name='set_delivery_state'),
    url(r'^dv-(?P<delivery>[^./]+)/set-name/(?P<name>.+)$', views.set_delivery_name, name='set_delivery_name'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/set-state/(?P<state>[A-Za-z]+)$',
        views.set_subgroup_state_for_delivery, name='set_subgroup_state_for_delivery'),
    url(r'^dv-(?P<delivery>[^./]+)/archive\.(?P<suffix>[^./]+)$', views.get_archive, name='get_archive'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/regulation$', views.adjust_subgroup, name='subgroup_regulation'),

    url(r'^candidacy$', views.candidacy, name='candidacy'),
    url(r'^cd-(?P<candidacy>[^./]+)/cancel$', views.cancel_candidacy, name='cancel_candidacy'),
    url(r'^cd-(?P<candidacy>[^./]+)/set-response/(?P<response>[YN])$', views.validate_candidacy, name='validate_candidacy'),
    url(r'^nw-(?P<network>[^/]+)/leave$', views.leave_network, name='leave_network'),
    url(r'^new-cd/sg-(?P<subgroup>[^./]+)$', views.create_candidacy, name='create_candidacy'),

    url(r'^dv-(?P<delivery>[^./]+).html$', views.view_purchases_html, name='view_all_purchases_html'),
    url(r'^dv-(?P<delivery>[^./]+)/table.pdf$', views.view_purchases_latex, name='view_all_purchases_latex'),
    url(r'^dv-(?P<delivery>[^./]+)/cards.pdf$', views.view_cards_latex, name='view_all_cards_latex'),
    url(r'^dv-(?P<delivery>[^./]+).xlsx$', views.view_purchases_xlsx, name='view_all_purchases_xlsx'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+).html$',
        views.view_purchases_html, name='view_subgroup_purchases_html'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+).xlsx$',
        views.view_purchases_xlsx, name='view_subgroup_purchases_xlsx'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/table.pdf$',
        views.view_purchases_latex, name='view_subgroup_purchases_latex'),
    url(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/cards.pdf$',
        views.view_cards_latex, name='view_subgroup_cards_latex'),

    url(r'^dv-(?P<delivery>[^./]+)/delete$', views.delete_archived_delivery, name='delete_archived_delivery'),
    url(r'^nw-(?P<network>[^./]+)/delete-empty-archives$', views.delete_all_archived_deliveries, name='delete_all_archived_deliveries'),

    url(r'^nw-(?P<network>[^./]+)/emails$', views.view_emails, name='emails_network'),
    url(r'^sg-(?P<subgroup>[^./]+)/emails$', views.view_emails, name='emails_subgroup'),

    url(r'^nw-(?P<network>[^./]+)/phones$', views.view_phones, name='phones_network'),
    url(r'^sg-(?P<subgroup>[^./]+)/phones$', views.view_phones, name='phones_subgroup'),

    url(r'^history$', views.view_history, name='view_history'),
    url(r'^journal$', views.journal, name='view_journal'),
    url(r'^charte.html$', TemplateView.as_view(template_name='charte.html'), name='charte'),

    url(r'^admin/', include(admin.site.urls), name='admin'),

    url(r'^accounts/register$', views.user_register, name="user_register"),
    url(r'^accounts/registration_post.html$', views.user_register_post, name="registration_post"),
    url(r'^accounts/password/reset/?$', views.password_reset, name="password_reset"),
    url(r'^accounts/', include('registration.backends.simple.urls')),

    url(r'^add-phone-number/(?P<phone>[^./]+)$', views.phone.add_phone_number, name="add_phone_number"),

    url('^markdown/', include("django_markdown.urls")),
]
