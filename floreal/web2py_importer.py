#!/usr/bin/python

"""Migrate old passwords DB from the sqlite Web2Py DB to Django"""

import sqlite3
import django
from . import models

WEB2PY_PATH = "/home/fabien/src/web2py"
RQ = "SELECT email, first_name, last_name, password, name FROM auth_user, circles where circles.id==auth_user.circle"

def run():
    django.setup()
    c = sqlite3.connect(WEB2PY_PATH+"/applications/floreal/databases/storage.sqlite").cursor()
    for email, first_name, last_name, password, circle in c.execute(RQ).fetchall():
        if first_name == "Extra":
            continue
        print "Importing %s %s from %s" % (first_name, last_name, circle)
        models.LegacyPassword.objects.create(email=email, password=password, circle=circle)
    print "done"

run()