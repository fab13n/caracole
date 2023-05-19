#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django.urls import include, re_path, path, register_converter
from django.contrib import admin
from django.views.generic import TemplateView
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from . import views
import debug_toolbar
import impersonate.urls


from wagtail.core import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls


class Identifier(object):
    regex = '[0-9A-Za-z_]+'

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value

register_converter(Identifier, "id")


urlpatterns = [
    # Security: sort what's served inside the page
    path('admin/reseaux.html', views.admin, name='admin'),
    # Security: only users in networks I'm staff of
    path("admin/users.json", views.users_json, name='users_json'),
    # No security (AJAX query takes care of it)
    path("admin/users.html", views.users_html,name='users_html'),
    # Security managed by Django
    path('admin/db/', admin.site.urls),
    # Security: review
    path('admin/impersonate/', include(impersonate.urls)),
    # Security: only global staff
    path('admin/journal', views.journal, name='view_journal'),
    # Security: only lists networks one's staff of
    path('admin/candidacies', views.manage_candidacies, name='manage_candidacies'),

    # Everyone, logged and unlogged
    path('', views.index, name='index'),

    # Security: based on memberhsip.is_buyer
    path('orders.html', views.orders, name='orders'),
    path("orders/products.json", views.active_products, name='active_products'),

    # Security: Only me
    path('user.html', views.user, name='user'),

    # Security: logged in + visibility
    path('nw-<id:network>/presentation.html', views.reseau, name='reseau'),

    # Security: check both get and post
    path('dv-<id:delivery>/buy.html', views.buy, name='buy'),
    path('dv-<id:delivery>/preview.html', views.buy, kwargs={'preview': True}, name='preview'),
    path('dv-<id:delivery>/buy.json', views.view_purchases_json, kwargs={"user": True}, name='user_purchases_json'),

    path('new-nw/<path:nw_name>', views.create_network, name='create_network'),
    path('new-dv/nw-<id:network>/list', views.list_delivery_models, name='list_delivery_models'),
    path('new-dv/nw-<id:network>/list-all', views.list_delivery_models, kwargs={'all_networks': True}, name='list_delivery_models_all_networks'),
    #why?
    path('new-dv/nw-<id:network>/list-producer', views.list_delivery_models, kwargs={'producer': True}, name='list_delivery_models_producer'),
    path('new-dv/nw-<id:network>/dv-<dv_model>', views.create_delivery, name='create_delivery_copy'),
    path('new-dv/nw-<id:network>', views.create_delivery, kwargs={'dv_model': None}, name='create_empty_delivery'),

    path('nw-<id:network>/archives', views.archived_deliveries, name='archived_deliveries'),
    path('nw-<id:network>/edit-description', views.network_description_and_image, name='edit_network_description'),
    path('u-<id:user>/edit-description', views.user_description_and_image, name='edit_user_description'),
    re_path(r'^nw-(?P<network>[0-9]+)/all-deliveries/(?P<states>[A-Z]+)\.html$', views.all_deliveries_html, name='all_deliveries_html'),
    re_path(r'^nw-(?P<network>[0-9]+)/all-deliveries/(?P<states>[A-Z]+)\.pdf$', views.all_deliveries_latex, name='all_deliveries_latex'),
    path('nw-<id:network>/invoice-mail-form', views.invoice_mail_form, name='invoice_mail_form'),

    path('admin/dv-<id:delivery>/purchases', views.edit_delivery_purchases, kwargs={'try_subgroup': True}, name='edit_delivery_purchases'),
    path('admin/dv-<id:delivery>/all_purchases', views.edit_delivery_purchases, kwargs={'try_subgroup': False}, name='edit_delivery_all_purchases'),
    path('admin/dv-<id:delivery>/edit', views.edit_delivery_products, name='edit_delivery_products'),


    # API calls
    path('dv-<id:delivery>/set-state/<state>', views.set_delivery_state, name='set_delivery_state'),
    re_path(r'^dv-(?P<delivery>[0-9]+)/set-name/(?P<name>.*)$', views.set_delivery_name, name='set_delivery_name'),
    path('edit-message/<id:id>', views.set_message, name='edit_message'),
    path('new-message/<destination>', views.set_message, name='set_message'),
    path('set-message', views.set_message),
    path('unset-message/<id:id>', views.unset_message, name='unset_message'),
    path('nw-<id:network>/set-visibility/<val>', views.set_network_visibility, name='set_network_visibility'),
    path('nw-<id:network>/set-validation/<val>', views.set_network_validation, name='set_network_validation'),
    path('candidacy/nw-<network>/u-<user>/cancel', views.cancel_candidacy, name='cancel_candidacy'),
    path('candidacy/nw-<network>/u-<user>/set-response/<response>', views.validate_candidacy, name='validate_candidacy'),
    path('nw-<id:network>/leave', views.leave_network, name='leave_network'),
    path('candidacy/nw-<id:network>', views.create_candidacy, name='create_candidacy'),


    path('dv-<id:delivery>.html', views.view_purchases_html, name='view_delivery_purchases_html'),
    path('dv-<id:delivery>.pdf', views.view_purchases_latex_table, name='view_delivery_purchases_latex'),
    path('dv-<id:delivery>-cards.pdf', views.view_purchases_latex_cards, name='view_delivery_purchases_cards'),
    path('dv-<id:delivery>.xlsx', views.view_purchases_xlsx, name='view_delivery_purchases_xlsx'),
    path('dv-<id:delivery>/purchases.json', views.view_purchases_json, name='view_delivery_purchases_json'),
    path('dv-<id:delivery>/sg-<id:subgroup>/purchases.json', views.view_purchases_json, name='view_delivery_purchases_json'),
    path('admin/dv-<id:delivery>/products.json', views.delivery_products_json, name='delivery_json'),

    path('dv-<id:delivery>/delete', views.delete_archived_delivery, name='delete_archived_delivery'),
    path('nw-<id:network>/delete-empty-archives', views.delete_all_archived_deliveries, name='delete_all_archived_deliveries'),

    path('nw-<id:network>/directory', views.view_directory, name='directory_network'),
    path('sg-<id:subgroup>/directory', views.view_directory, name='directory_subgroup'),

    path('history', views.view_history, name='view_history'),

    path('accounts/register', views.user_register, name="user_register"),
    path('accounts/update', views.user_update, name="user_update"),
    # TODO Test usefulness of final /
    re_path('^accounts/password/reset/?$', PasswordResetView.as_view(), name="password_reset"),
    re_path('^accounts/password/reset_done/?$', PasswordResetDoneView.as_view(), name="password_reset_done"),
    path('accounts/', include('registration.backends.simple.urls')),
    path('accounts/deactivate', views.user_deactivate, name='user_deactivate'),

    # TODO what for!?
    path('edit/<title>/<path:target>', views.editor, name='editor'),

    path('__debug__/', include(debug_toolbar.urls)),

    path('map.html', views.map, name='map'),

    path('admin/pages/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),

    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's serving mechanism
    path('pages/', include(wagtail_urls)),

    path("bestof", views.bestof),

]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
