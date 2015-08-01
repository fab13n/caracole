#!/bin/bash
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
# rm $DIR/db.sqlite3
$DIR/manage.py syncdb --noinput
export DJANGO_SETTINGS_MODULE=caracole.settings
python -m floreal.web2py_importer
