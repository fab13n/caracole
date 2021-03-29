#!/usr/bin/env python3
from django.shortcuts import render, redirect

from floreal import models as m


def has_number(u):
    return m.FlorealUser.objects.filter(user_id=u.id).exists()


def add_phone_number(request, phone):
    user = request.user
    m.FlorealUser.objects.create(user=user, phone=phone)
    m.JournalEntry.log(request.user, "Filled their phone number")
    return redirect('index')
