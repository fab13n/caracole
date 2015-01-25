#!/usr/bin/python
# -*- coding: utf8 -*-

"""Migrate old passwords DB from the sqlite Web2Py DB to Django"""

import sqlite3
import django
from . import models

DB_PATH = "/home/fabien/src/web2py/applications/floreal/databases/storage.sqlite"
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
        print "* Importing %s %s from %s" % (first_name, last_name, circle)
        # Store legacy password
        models.LegacyPassword.objects.create(email=email, password=password, circle=circle)

        # Retrieve user
        try:
            models.User.objects.get(username=email)
            print "\t* [already there]"
        except models.User.DoesNotExist:
            print "\t* Creating it"
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
                print "\t* Joining subgroup %s" % sg.name
            except models.Subgroup.DoesNotExist:
                print "\t* Creating and joining subgroup %s" % circle
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
        print "* promoting %s as admin of subgroup %s" % (email, circle)
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
        print "* promoting '%s' as network admin" % email
        u = models.User.objects.get(username=email)
        u.is_staff = True
        nw.staff.add(u)
        nw.save()
        u.save()

def import_purchases():
    DV = "SELECT id, name, is_open, date FROM deliveries"
    for (dv_id, dv_name, is_open, date) in cx.cursor().execute(DV).fetchall():
        print "* Create delivery %s" % dv_name
        dv = models.Delivery.objects.create(name=dv_name, network=nw, state='O' if is_open!='F' else 'C')
        PD = "SELECT id, name, package_quantity, price, unit FROM products WHERE delivery=%s" % dv_id
        for (pd_id, pd_name, package_quantity, price, unit) in cx.cursor().execute(PD).fetchall():
            print "\t* Create product %s at EUR%s/%s" % (pd_name, price, unit)
            pd = models.Product.objects.create(name=pd_name, delivery=dv, price=price,
                                               quantity_per_package=package_quantity, unit=unit, quantity_limit=None)
            PC = "SELECT email, circles.name, granted_quantity FROM auth_user, purchases, circles " \
                 "WHERE product=%s AND user=auth_user.id AND circles.id=circle" % pd_id
            for (email, circle_name, qty) in cx.cursor().execute(PC).fetchall():
                print "\t\t* Bought (%s %s) by %s from %s" % (qty, unit, email or "extra", circle_name)
                if email:
                    u = models.User.objects.get(email=email)
                else:
                    # Retrieve extra user
                    sg = models.Subgroup.objects.get(name=circle_name)
                    u = sg.extra_user
                models.Purchase.objects.create(user=u, product=pd, ordered=qty, granted=qty)

def run():
    create_users()
    promote_subgroup_admins()
    promote_network_admins()
    import_purchases()

run()