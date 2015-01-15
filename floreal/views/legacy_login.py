"""
Support for alternative passwords table, imported from a Web2PY previous
version of the site.
"""
import hmac
from hashlib import sha512

from django.shortcuts import render_to_response, redirect
from django.core.context_processors import csrf
from django.contrib.auth import login
from django import forms

from .. import models as m


KEY = "d143d4a7-1c24-42d5-a615-ae951bb1b600"


def check_legacy_password(email, password):
    try:
        stored = m.LegacyPassword.objects.get(email=email, None)
        (digest_alg, salt, stored_digest) = stored.password.split("$")
        digest = hmac.new(KEY+salt, password, sha512).hexdigest()
        return digest == stored_digest
    except m.LegacyPassword.DoesNotExist:
        print "Not a web2py user"
        return false


def migrate_password(u, password):
    """Write the password in the main auth system, remember it has been migrated."""
    u.set_password(password)
    u.save()
    lp = m.LegacyPassword.objects.get(email=u.username)
    lp.migrated = True
    lp.save()


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.PasswordInput()

    # TODO: validate on fields and raise Form.ValidationExceptions
    def is_valid(self):
        username = self.cleaned_data['email']
        password = self.cleaned_data['password']
        print "%s / %s" % (username, password)
        u = m.User.objects.get(username=username)
        if u.check_password(password):
            print "User %s authenticated with Django" % username
            return True
        elif check_legacy_password(username, password):
            migrate_password(u, password)
            return True
        else:
            return False


def user_login(request):
    """
    Display the login form and handle the login action.
    """
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("/")
    else:
        form = LoginForm(request)

    vars = {
        'form': form,
    }
    vars.update(csrf(request))
    return render_to_response("register/login.html", vars)