#!/usr/bin/python3

from django.contrib import admin
from . import models as m

@admin.register(m.FlorealUser)
class FlorealUserAdmin(admin.ModelAdmin):
    search_fields=('user__first_name', 'user__last_name', 'user__email')

admin.site.register(
    (
        m.Network,
        m.Delivery,
        m.Product,
        m.Purchase,
        m.Plural,
        m.AdminMessage,
        m.NetworkMembership,
        m.NetworkSubgroup,
        m.JournalEntry,
        m.Bestof,
    )
)
