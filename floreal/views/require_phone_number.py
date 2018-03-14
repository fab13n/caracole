#!/usr/bin/env python3
# -*-coding: utf-8 -*-
from django.shortcuts import render, redirect

from floreal import models as m


def has_number(u):
    return m.UserPhones.objects.filter(user_id=u.id).exists()


def add_phone_number(request, phone):
    user = request.user
    m.UserPhones.objects.create(user=user, phone=phone)
    m.JournalEntry.log(request.user, "Filled their phone number")
    return redirect('index')