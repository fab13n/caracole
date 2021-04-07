#!/usr/bin/python3

from django.contrib import admin
from . import models as m


admin.site.register(
    (
        m.Network,
        m.Delivery,
        m.Product,
        m.Purchase,
        m.Plural,
        m.FlorealUser,
        m.AdminMessage,
        m.NetworkMembership,
        m.NetworkSubgroup,
        m.JournalEntry,
    )
)
