#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.urls import include, re_path, path
from django.contrib import admin
from django.views.generic import TemplateView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from . import views

urlpatterns = [
    path('', views.index, name='index'),

    path('new-nw/<nw_name>/<sg_name>', views.create_network, name='create_network'),
    path('new-dv/nw-<network>/list', views.list_delivery_models, name='list_delivery_models'),
    path('new-dv/nw-<network>/list-all', views.list_delivery_models, kwargs={'all_networks': True}, name='list_delivery_models_all_networks'),
    path('new-dv/nw-<network>/list-producer', views.list_delivery_models, kwargs={'producer': True}, name='list_delivery_models_producer'),
    path('new-dv/nw-<network>/dv-<dv_model>', views.create_delivery, name='create_delivery_copy'),
    path('new-dv/nw-<network>', views.create_delivery, kwargs={'dv_model': None}, name='create_empty_delivery'),
    
    path('nw-<network>', views.network_admin, name='network_admin'),
    path('nw-<network>/producer', views.producer, name='producer'),
    path('nw-<network>/archives', views.archived_deliveries, name='archived_deliveries'),
    path('nw-<network>/edit-description', views.edit_network_description, name='edit_network_description'),
    re_path(r'^nw-(?P<network>[^/]+)/all-deliveries/(?P<states>[A-Z]+)$', views.all_deliveries_html, name='all_deliveries_html'),
    re_path(r'^nw-(?P<network>[^/]+)/all-deliveries/(?P<states>[A-Z]+)\.pdf$', views.all_deliveries_latex, name='all_deliveries_latex'),
    path('nw-<network>/invoice-mail-form', views.invoice_mail_form, name='invoice_mail_form'),

    re_path('^dv-(?P<delivery>[^./]+)$', views.edit_user_purchases, name='edit_user_purchases'),
    path('dv-<delivery>/staff', views.edit_delivery_staff, name='edit_delivery_staff'),
    path('dv-<delivery>/staff/purchases/nw-<network>', views.edit_delivery_purchases, name='edit_delivery_purchases'),
    path('dv-<delivery>/staff/products', views.edit_delivery_products, name='edit_delivery_products'),
    path('dv-<delivery>/staff/products.json', views.delivery_products_json, name='delivery_json'),
    
    path('dv-<delivery>/set-state/<state>', views.set_delivery_state, name='set_delivery_state'),
    path('dv-<delivery>/set-name/<name>', views.set_delivery_name, name='set_delivery_name'),
    path('dv-<delivery>/archive.<suffix>', views.get_archive, name='get_archive'),
 
    path('candidacy', views.candidacy, name='candidacy'),
    path('cd-<candidacy>/cancel', views.cancel_candidacy, name='cancel_candidacy'),
    path('cd-<candidacy>/set-response/<response>', views.validate_candidacy, name='validate_candidacy'),
    path('nw-<network>/leave', views.leave_network, name='leave_network'),
    path('new-cd/nw-<network>', views.create_candidacy, name='create_candidacy'),
    path('candidacy/staff', views.manage_candidacies, name='manage_candidacies'),

    re_path('^nw-(?P<network>[^/-]+)-dv-(?P<delivery>[^./-]+).html$', views.view_purchases_html, name='view_network_purchases_html'),
    re_path('^nw-(?P<network>[^/-]+)-dv-(?P<delivery>[^./-]+).pdf$', views.view_purchases_latex, name='view_network_purchases_latex'),
    re_path('^nw-(?P<network>[^/-]+)-dv-(?P<delivery>[^./-]+)-cards.pdf$', views.view_purchases_cards, name='view_network_purchases_cards'),
    re_path('^nw-(?P<network>[^/-]+)-dv-(?P<delivery>[^./-]+).xlsx$', views.view_purchases_xlsx, name='view_network_purchases_xlsx'),
    re_path('^nw-(?P<network>[^/-]+)-dv-(?P<delivery>[^./-]+).json$', views.view_purchases_json, name='view_network_purchases_json'),

    re_path('^dv-(?P<delivery>[^./]+).html$', views.view_purchases_html, name='view_delivery_purchases_html'),
    re_path('^dv-(?P<delivery>[^./]+).pdf$', views.view_purchases_latex, name='view_delivery_purchases_latex'),
    re_path('^dv-(?P<delivery>[^./-]+)-cards.pdf$', views.view_purchases_cards, name='view_delivery_purchases_cards'),
    re_path('^dv-(?P<delivery>[^./]+).xlsx$', views.view_purchases_xlsx, name='view_delivery_purchases_xlsx'),
    re_path('^dv-(?P<delivery>[^./-]+).json$', views.view_purchases_json, name='view_delivery_purchases_json'),
    
    path('dv-<delivery>/delete', views.delete_archived_delivery, name='delete_archived_delivery'),
    path('nw-<network>/delete-empty-archives', views.delete_all_archived_deliveries, name='delete_all_archived_deliveries'),

    path('nw-<network>/emails', views.view_emails, name='emails_network'),
    path('nw-<network>/emails.pdf', views.view_emails_pdf, name='emails_network_pdf'),

    path('nw-<network>/phones', views.view_phones, name='phones_network'),
    
    path('history', views.view_history, name='view_history'),
    path('journal', views.journal, name='view_journal'),
    path('charte.html', TemplateView.as_view(template_name='charte.html'), name='charte'),

    path('admin', admin.site.urls),
    path('impersonate/', include('impersonate.urls')),
 
    path('accounts/register', views.user_register, name="user_register"),
    path('accounts/registration_post.html', views.candidacy, name="registration_post"),
    # TODO Test usefulness of final /
    re_path('^accounts/password/reset/?$', PasswordResetView.as_view(), name="password_reset"),
    re_path('^accounts/password/reset_done/?$', PasswordResetDoneView.as_view(), name="password_reset_done"),
    path('accounts/', include('registration.backends.simple.urls')),

    path('add-phone-number/<phone>', views.phone.add_phone_number, name="add_phone_number"),
    path('edit/<title>/<path:target>', views.editor, name='editor'),
    path('set-message', views.set_message, name='set_message'),
    path('unset-message/<int:id>', views.unset_message, name='unset_message'),

    path("users.json", views.users_json, name='users_json'),
    path("users.html", views.users_html,name='users_html')
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
