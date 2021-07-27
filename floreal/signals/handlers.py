from django.db.models.signals import pre_save
from django.dispatch import receiver
from .. import models as m
import registration.signals

# @receiver(pre_save, sender=registration.signals.user_registered)
# def user_registered(sender, user, **kwargs):
#     print("User registered", repr(kwargs))
#     m.JournalEntry.log(user, "User created")
