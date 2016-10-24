#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.views import password_reset as original_password_reset
from django.http import HttpResponseForbidden


def password_reset(request, password_reset_form=PasswordResetForm, post_reset_redirect='auth_password_reset_done', **kwargs):
    if request.method == "POST":
        form = password_reset_form(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if not User.objects.filter(is_active=True, email__iexact=email).exists():
                return HttpResponseForbidden(u"Cet e-mail ne correspond à aucun utilisateur Caracole !")

    return original_password_reset(request, password_reset_form=password_reset_form,
                                   post_reset_redirect=post_reset_redirect, **kwargs)
