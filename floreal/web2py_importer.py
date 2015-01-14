#!/usr/bin/python

"""Migrate old passwords DB from the sqlite Web2Py DB to Django"""

import sqlite3
import django
from . import models

DB_PATH = "/home/fabien/src/web2py/applications/floreal/databases/storage.sqlite"
DV_NAME = "ancienne"
NW_NAME = "Floreal"

# This way hopefully I won't commit it
with open("/home/fabien/scratch/floreal-default-password") as f:
    DEFAULT_PASSWORD = f.read().strip()

django.setup()
cx = sqlite3.connect(DB_PATH)

try:
    nw = models.Network.objects.get(name=NW_NAME)
except Exception:
    nw = models.Network.objects.create(name=NW_NAME)


def create_users():
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
            models.User.objects.get(username=email)
            print "\t * [already there]"
        except models.User.DoesNotExist:
            print "\t * Creating it"
            user = models.User.objects.create(username=email,
                                              first_name=first_name,
                                              last_name=last_name,
                                              email=email,
                                              is_staff=False,
                                              is_active=True)
            user.set_password(DEFAULT_PASSWORD)
            user.save()
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
        u = models.User.objects.get(username=email)
        u.is_staff = True
        nw.staff.add(u)
        nw.save()
        u.save()


def import_products():
    RQ = "SELECT name, max_quantity, package_quantity, unit, price " \
         "FROM past_products"
    try:
        dv = models.Delivery.objects.get(name=DV_NAME, network=nw)
    except Exception:
        print "Creating delivery %s" % DV_NAME
        dv = models.Delivery.objects.create(name=DV_NAME, network=nw)
    for (name, quantity_limit, quantity_per_package, unit, price) in cx.cursor().execute(RQ).fetchall():
        if models.Product.objects.filter(name=name):
            print "Product %s already exists" % name
        else:
            print "Importing product %s" % name
            models.Product.objects.create(name=name,
                                          quantity_limit=quantity_limit,
                                          quantity_per_package=quantity_per_package,
                                          unit=unit,
                                          price=price,
                                          delivery=dv)

create_users()
promote_subgroup_admins()
promote_network_admins()
import_products()