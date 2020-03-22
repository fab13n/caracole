#!/usr/bin/python
# -*- coding: utf8 -*-

import re

from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth import authenticate, login

from .. import models as m


class RegistrationForm(forms.Form):
    email = forms.EmailField(label='Adresse e-mail')
    first_name = forms.CharField(label='Prénom')
    last_name = forms.CharField(label='Nom de famille')
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Mot de passe (à nouveau)', widget=forms.PasswordInput())

    def clean_subgroup(self):
        """Check that no network is multi-subscribed"""
        seen_networks = set()
        subgroups = self.cleaned_data['subgroup']
        for sg in subgroups:
            if sg.network in seen_networks:
                raise forms.ValidationError("Ne pas sélectionner plus d'un sous-groupe par réseau.")
            else:
                seen_networks.add(sg.network)
        return subgroups

    def clean_email(self):
        email = self.cleaned_data['email']
        if m.User.objects.filter(email=email).count():
            raise forms.ValidationError('Cet e-mail est déjà enregistré.')
        return email

    def clean_password2(self):
        if 'password1' in self.cleaned_data:
            password1 = self.cleaned_data['password1']
            password2 = self.cleaned_data['password2']
            if password1 == password2:
                return password1
        raise forms.ValidationError('Les mots de passe ne correspondent pas.')

    def clean_first_name(self):
        capitalized = self.cleaned_data['first_name'].strip().lower().title()
        if not capitalized:
            raise forms.ValidationError('Entrer un prénom.')
        cleaned = re.sub(r"\bEt\b", "et", capitalized)
        return cleaned

    def clean_last_name(self):
        capitalized = self.cleaned_data['last_name'].strip().lower().title()
        if not capitalized:
            raise forms.ValidationError('Entrer un nom de famille.')
        cleaned = re.sub(r"\bD(['e])\b", r"d\1", capitalized)  # Particules are lowercased in French
        return cleaned


def user_register(request):
    """
    Register a new user: username is defined to be the same as email,
    at least one subgroup must be registered, and if several subgroups
    are selected, there may be only one per network.
    :param request: HTTP request, GET or POST
    :return: HTML form or redirection to the home page.
    """

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            email = d['email']
            user = m.User.objects.create(
                username=email,
                first_name=d['first_name'],
                last_name=d['last_name'],
                email=email,
            )
            user.set_password(d['password1'])
            user.save()

            m.JournalEntry.log(user, "Created an account: %s %s, %s", user.first_name, user.last_name, user.username)

            # Auto-login
            new_user = authenticate(username=d['email'], password=d['password1'])
            login(request, new_user)

            return HttpResponseRedirect('registration_post.html')
        else:  # invalid form
            d = form.data
            m.JournalEntry.log(None, "Failed account creation for %s %s (%s)", d['first_name'], d['last_name'], d['email'])
            return render(request, 'registration/registration_form.html', {'form': form})
    else:
        return render(request, 'registration/registration_form.html', {'form': RegistrationForm()})


def user_register_post(request):
    return render(request, 'registration/registration_post.html', {})
