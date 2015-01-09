#!/usr/bin/python

"""Migrate old passwords DB from the sqlite Web2Py DB to Django"""

import sqlite3
import django
from . import models

WEB2PY_PATH = "/home/fabien/src/web2py"

# This way hopefully I won't commit it
with open("/home/fabien/scratch/floreal-default-password") as f:
    DEFAULT_PASSWORD = f.read().strip()
django.setup()
cx = sqlite3.connect(WEB2PY_PATH+"/applications/floreal/databases/storage.sqlite")
nw = models.Network.objects.get(name='Floreal')

def create_them():
    RQ = "SELECT email, first_name, last_name, password, name FROM auth_user, circles WHERE circles.id==auth_user.circle"
    models.LegacyPassword.objects.all().delete()
    for email, first_name, last_name, password, circle in cx.cursor().execute(RQ).fetchall():
        if first_name == "Extra":
            continue
        print "Importing %s %s from %s" % (first_name, last_name, circle)
        # Store legacy password
        models.LegacyPassword.objects.create(email=email, password=password, circle=circle)

        # Retrieve user
        try:
            user = models.User.objects.get(username=email)
            print "\t * [already there]"
        except models.User.DoesNotExist:
            print "\t * Creating it"
            user = models.User.objects.create(username=email,
                                              first_name=first_name,
                                              last_name=last_name,
                                              email=email,
                                              is_staff=False,
                                              is_active=True,
                                              password=DEFAULT_PASSWORD)
            try:
                sg = models.Subgroup.objects.get(name=circle, network=nw)
                print "\t * Joining subgroup %s" % sg.name
            except models.Subgroup.DoesNotExist:
                print "\t * Creating and joining subgroup %s" % circle
                sg = models.Subgroup.objects.create(name=circle, network=nw)
            sg.users.add(user)
            sg.save()

def promote_subgroup_admins():
    RQ = "SELECT email, circles.name " \
         "FROM auth_user, auth_membership, auth_group, circles  " \
         "WHERE auth_membership.user_id==auth_user.id " \
         "AND group_id==auth_group.id " \
         "AND auth_group.role=='floreal_admin' "\
         "AND auth_user.circle==circles.id"

    for email, circle in cx.cursor().execute(RQ).fetchall():
        print "promoting %s as admin of subgroup %s" % (email, circle)
        sg = models.Subgroup.objects.get(name=circle)
        sg.staff.add(models.User.objects.get(username=email))
        sg.save()

def promote_network_admins():
    RQ = "SELECT email " \
         "FROM auth_user, auth_membership, auth_group " \
         "WHERE auth_membership.user_id==auth_user.id " \
         "AND group_id==auth_group.id " \
         "AND auth_group.role=='floreal_global_admin' "

    for (email,) in cx.cursor().execute(RQ).fetchall():
        print "promoting '%s' as network admin" % email
        u=models.User.objects.get(username=email)
        u.is_staff=True
        nw.staff.add(u)
        nw.save()
        u.save()

create_them()
promote_subgroup_admins()
promote_network_admins()