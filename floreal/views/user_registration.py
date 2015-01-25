#!/usr/bin/python
# -*- coding: utf8 -*-

from django import forms
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .. import models as m


class RegistrationForm(forms.Form):
    email = forms.EmailField(label='Adresse e-mail')
    first_name = forms.CharField(label='Prénom')
    last_name = forms.CharField(label='Nom de famille')
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Mot de passe (à nouveau)', widget=forms.PasswordInput())
    subgroup = forms.ModelMultipleChoiceField(m.Subgroup.objects.all(), label='Réseau et sous-groupe')

    def clean_subgroup(self):
        """Check that no network is multi-subscribed"""
        seen_networks = set()
        subgroups = self.cleaned_data['subgroup']
        for sg in subgroups:
            if sg.network in seen_networks:
                raise forms.ValidationError("Ne pas sélectionner plus d'un sous-groupe par réseau.")
            else:
                seen_networks.add(sg.network)
        if len(seen_networks) == 0:
            raise forms.ValidationError("Souscrire à au moins un sous-groupe.")
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
            sg = m.Subgroup.objects.get(id=d['subgroup'])
            sg.users.add(user)
            sg.save()
            return HttpResponseRedirect('index')
        else:  # invalid form
            return render(request, 'registration/registration_form.html', {'form': form})
    else:
        return render(request, 'registration/registration_form.html', {'form': RegistrationForm()})
