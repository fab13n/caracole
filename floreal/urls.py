#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.conf.urls import patterns, include, url
from django.contrib import admin
from . import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^admin/', include(admin.site.urls), name='admin'),
    url(r'^accounts/register$', views.user_register, name="user_register"),
    url(r'^accounts/registration_post.html$', views.user_register_post, name="registration_post"),
    url(r'^accounts/', include('registration.backends.simple.urls')),
    url(r'^staff/create/delivery/(?P<network>[0-9]+)$', views.create_delivery, name='create_delivery'),
    url(r'^staff/delivery/(?P<delivery>[0-9]+)/(?P<state>[A-Za-z]+)$', views.set_delivery_state, name='set_delivery_state'),
    url(r'^staff/edit/adjust/(?P<delivery>[0-9]+)$', views.adjust_subgroup, name='adjust_subgroup'),
    url(r'^staff/edit/delivery/(?P<delivery>[0-9]+)$', views.edit_delivery_products, name='edit_delivery_products'),
    url(r'^staff/edit/membership/(?P<network>[0-9]+)$', views.edit_user_memberships, name='edit_user_memberships'),
    url(r'^staff/edit/state_for_subgroup$', views.set_subgroup_state_for_delivery, name='set_subgroup_state_for_delivery'),
    url(r'^staff/view/purchases/(?P<delivery>[0-9]+).html$', views.view_delivery_purchases_html, name='view_delivery_purchases_html'),
    url(r'^staff/view/purchases/(?P<delivery>[0-9]+).pdf$', views.view_delivery_purchases_latex, name='view_delivery_purchases_latex'),
    url(r'^staff/view/purchases/(?P<delivery>[0-9]+).xlsx$', views.view_delivery_purchases_xlsx, name='view_delivery_purchases_xlsx'),
    url(r'^staff/view/purchases/subgroup/(?P<delivery>[0-9]+).html$', views.view_subgroup_purchases_html, name='view_subgroup_purchases_html'),
    url(r'^staff/view/purchases/subgroup/(?P<delivery>[0-9]+).pdf$', views.view_subgroup_purchases_latex, name='view_subgroup_purchases_latex'),
    url(r'^staff/view/purchases/cards/(?P<delivery>[0-9]+).pdf$', views.view_subgroup_cards_latex, name='view_subgroup_cards_latex'),
    url(r'^staff/view/purchases/subgroup/(?P<delivery>[0-9]+).xlsx$', views.view_subgroup_purchases_xlsx, name='view_subgroup_purchases_xlsx'),
    url(r'^staff/edit/purchases/subgroup/(?P<delivery>[0-9]+)$', views.edit_subgroup_purchases, name='edit_subgroup_purchases'),
    url(r'^purchases/(?P<delivery>[0-9]+)$', views.edit_user_purchases, name='edit_user_purchases'),
    url(r'^emails/network/(?P<network>[0-9]+)$', views.view_emails, name='emails_network'),
    url(r'^emails/subgroup/(?P<subgroup>[0-9]+)$', views.view_emails, name='emails_subgroup'),
    url(r'^history/(?P<network>[0-9]+)$', views.view_history, name='view_history'),
)
