from django.shortcuts import render_to_response, redirect

from floreal import models as m


def has_number(u):
    return m.UserPhones.objects.filter(user_id=u.id).exists()


def add_phone_number(request, phone):
    user = request.user
    m.UserPhones.objects.create(user=user, phone=phone)
    return redirect('index')