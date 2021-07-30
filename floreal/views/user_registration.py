#!/usr/bin/python3

import re

from django import forms
from django.forms import widgets
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout

from .. import models as m





class UpdateForm(forms.Form):
    first_name = forms.CharField(label='Prénom')
    last_name = forms.CharField(label='Nom de famille')
    phone = forms.CharField(label="Téléphone", required=False)

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


class RegistrationForm(UpdateForm):
    email = forms.EmailField(label='Adresse e-mail')
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Mot de passe (à nouveau)', widget=forms.PasswordInput())

    def clean_email(self):
        email = self.cleaned_data['email']
        if (prev_u := m.User.objects.filter(email=email).first()) is not None:
            if prev_u.is_active:
                raise forms.ValidationError('Cet e-mail est déjà enregistré.')
            else:
                # TODO: change the old User's email, to respect uniqueness constraint.
                raise forms.ValidationError('Vous vous êtes désinscrit. Contactez un administrateur si vous souhaitez revenir.')
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
            m.FlorealUser.objects.create(user=user, phone=d['phone'])


            m.JournalEntry.log(user, "Created an account u-%d: %s %s, %s", user.id, user.first_name, user.last_name, user.username)

            # Auto-login
            new_user = authenticate(username=d['email'], password=d['password1'])
            login(request, new_user)

            return HttpResponseRedirect('/#reseaux')
        else:  # invalid form
            d = form.data
            m.JournalEntry.log(None, "Failed account creation for %s %s (%s)", d['first_name'], d['last_name'], d['email'])
            return render(request, 'registration/registration_form.html', {'form': form})
    else:
        return render(request, 'registration/registration_form.html', {'form': RegistrationForm()})

def user_update(request):
    """
    """

    if request.method == 'POST':
        form = UpdateForm(request.POST)
        if form.is_valid() and form.has_changed():
            d = form.cleaned_data
            user = request.user
            user.first_name = d['first_name']
            user.last_name = d['last_name']
            user.florealuser.phone = d['phone']
            user.save()
            user.florealuser.save()
            m.JournalEntry.log(user, "Updated user account")
            return HttpResponseRedirect('/#reseaux')
        else:  # invalid form
            d = form.data
            m.JournalEntry.log(None, "Failed account update")
            return render(request, 'registration/update_form.html', {'form': form})
    else:
        u = request.user
        form = UpdateForm({
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'phone': u.florealuser.phone
        })
        return render(request, 'registration/update_form.html', {'form': form})


def user_deactivate(request):
    user = request.user
    if user.is_staff or user.is_superuser:
        return HttpResponse("Les admins ne doivent pas se désactiver tout seuls", status=400)
    user.networkmembership_set.filter(valid_until=None).update(valid_until=m.Now())
    user.is_active = False
    user.save()
    logout(request)
    return HttpResponseRedirect('index')
