#!/usr/bin/env bash

DB=database.sqlite3
sqlite3 $DB "INSERT INTO "django_migrations" VALUES(0,'auth','0001_initial','2016-01-01 0:00:00.0');"
sqlite3 $DB "INSERT INTO "django_migrations" VALUES(NULL,'registration','0001_initial','2016-01-01 0:00:00.0');"
./manage.py migrate
