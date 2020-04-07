#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.urls import include, re_path, path
from django.contrib import admin
from django.views.generic import TemplateView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView

#from django_markdown import urls as django_markdown_urls

from . import views

urlpatterns = [
    re_path(r'^$', views.index, name='index'),

    re_path(r'^new-nw/(?P<nw_name>[^./]+)/(?P<sg_name>[^./]+)$', views.create_network, name='create_network'),
    re_path(r'^new-dv/nw-(?P<network>[^./]+)/list$', views.list_delivery_models, name='list_delivery_models'),
    re_path(r'^new-dv/nw-(?P<network>[^./]+)/list-all$', views.list_delivery_models, kwargs={'all_networks': True}, name='list_delivery_models_all_networks'),
    re_path(r'^new-dv/nw-(?P<network>[^./]+)/dv-(?P<dv_model>[^./]+)$', views.create_delivery, name='create_delivery_copy'),
    re_path(r'^new-dv/nw-(?P<network>[^./]+)$', views.create_delivery, kwargs={'dv_model': None}, name='create_empty_delivery'),
    re_path(r'^new-sg/nw-(?P<network>[^./]+)/(?P<name>.+)$', views.create_subgroup, name='create_subgroup'),

    re_path(r'^nw-(?P<network>[^./]+)$', views.network_admin, name='network_admin'),
    re_path(r'^nw-(?P<network>[^./]+)/archives$', views.archived_deliveries, name='archived_deliveries'),
    re_path(r'^nw-(?P<network>[^./]+)/edit-users$', views.edit_user_memberships, name='edit_user_memberships'),
    re_path(r'^nw-(?P<network>[^./]+)/edit-users.json$', views.json_memberships, name='json_memberships'),
    re_path(r'^nw-(?P<network>[^./]+)/all-deliveries/(?P<states>[A-Z]+)$', views.all_deliveries_html, name='all_deliveries_html'),
    re_path(r'^nw-(?P<network>[^./]+)/all-deliveries/(?P<states>[A-Z]+).pdf$', views.all_deliveries_latex, name='all_deliveries_latex'),
    re_path(r'^nw-(?P<network>[^./]+)/invoice-mail/(?P<payment_date>.*)$', views.invoice_mail, name='invoice_mail'),

    re_path(r'^dv-(?P<delivery>[^./]+)$', views.edit_user_purchases, name='edit_user_purchases'),
    re_path(r'^dv-(?P<delivery>[^./]+)/staff$', views.edit_delivery, name='edit_delivery'),
    re_path(r'^dv-(?P<delivery>[^./]+)/edit-products$', views.edit_delivery_products, name='edit_delivery_products'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/edit$',
        views.edit_subgroup_purchases, name='edit_subgroup_purchases'),
    re_path(r'^dv-(?P<delivery>[^./]+)/set-state/(?P<state>[A-Za-z]+)$', views.set_delivery_state, name='set_delivery_state'),
    re_path(r'^dv-(?P<delivery>[^./]+)/set-name/(?P<name>.+)$', views.set_delivery_name, name='set_delivery_name'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/set-state/(?P<state>[A-Za-z]+)$',
        views.set_subgroup_state_for_delivery, name='set_subgroup_state_for_delivery'),
    re_path(r'^dv-(?P<delivery>[^./]+)/archive\.(?P<suffix>[^./]+)$', views.get_archive, name='get_archive'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/regulation$', views.adjust_subgroup, name='subgroup_regulation'),

    re_path(r'^candidacy$', views.candidacy, name='candidacy'),
    re_path(r'^cd-(?P<candidacy>[^./]+)/cancel$', views.cancel_candidacy, name='cancel_candidacy'),
    re_path(r'^cd-(?P<candidacy>[^./]+)/set-response/(?P<response>[YN])$', views.validate_candidacy, name='validate_candidacy'),
    re_path(r'^nw-(?P<network>[^/]+)/leave$', views.leave_network, name='leave_network'),
    re_path(r'^new-cd/sg-(?P<subgroup>[^./]+)$', views.create_candidacy, name='create_candidacy'),
    re_path(r'^nw-(?P<network>[^/]+)/candidacies', views.manage_candidacies, name='manage_candidacies'),

    re_path(r'^dv-(?P<delivery>[^./]+).html$', views.view_purchases_html, name='view_all_purchases_html'),
    re_path(r'^dv-(?P<delivery>[^./]+)/table.pdf$', views.view_purchases_latex, name='view_all_purchases_latex'),
    re_path(r'^dv-(?P<delivery>[^./]+)/cards.pdf$', views.view_cards_latex, name='view_all_cards_latex'),
    re_path(r'^dv-(?P<delivery>[^./]+).xlsx$', views.view_purchases_xlsx, name='view_all_purchases_xlsx'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+).html$',
        views.view_purchases_html, name='view_subgroup_purchases_html'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+).xlsx$',
        views.view_purchases_xlsx, name='view_subgroup_purchases_xlsx'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/table.pdf$',
        views.view_purchases_latex, name='view_subgroup_purchases_latex'),
    re_path(r'^dv-(?P<delivery>[^./]+)/sg-(?P<subgroup>[^./]+)/cards.pdf$',
        views.view_cards_latex, name='view_subgroup_cards_latex'),

    re_path(r'^dv-(?P<delivery>[^./]+)/delete$', views.delete_archived_delivery, name='delete_archived_delivery'),
    re_path(r'^nw-(?P<network>[^./]+)/delete-empty-archives$', views.delete_all_archived_deliveries, name='delete_all_archived_deliveries'),

    re_path(r'^nw-(?P<network>[^./]+)/emails$', views.view_emails, name='emails_network'),
    re_path(r'^sg-(?P<subgroup>[^./]+)/emails$', views.view_emails, name='emails_subgroup'),
    re_path(r'^nw-(?P<network>[^./]+)/emails.pdf$', views.view_emails_pdf, name='emails_network_pdf'),

    re_path(r'^nw-(?P<network>[^./]+)/phones$', views.view_phones, name='phones_network'),
    re_path(r'^sg-(?P<subgroup>[^./]+)/phones$', views.view_phones, name='phones_subgroup'),

    re_path(r'^history$', views.view_history, name='view_history'),
    re_path(r'^journal$', views.journal, name='view_journal'),
    re_path(r'^charte.html$', TemplateView.as_view(template_name='charte.html'), name='charte'),

    re_path(r'^admin/', admin.site.urls),
    re_path(r'^impersonate/', include('impersonate.urls')),
 
    re_path(r'^accounts/register$', views.user_register, name="user_register"),
    re_path(r'^accounts/registration_post.html$', views.user_register_post, name="registration_post"),
    re_path(r'^accounts/password/reset/?$', PasswordResetView.as_view(), name="password_reset"),
    re_path(r'accounts/password/reset_done/?$', PasswordResetDoneView.as_view(), name="password_reset_done"),
    re_path(r'^accounts/', include('registration.backends.simple.urls')),

    re_path(r'^add-phone-number/(?P<phone>[^./]+)$', views.phone.add_phone_number, name="add_phone_number"),

]
