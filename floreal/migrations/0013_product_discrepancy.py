#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-12-13 09:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0012_delivery_description'),
    ]

    operations = [
        migrations.RenameModel('Discrepancy', 'ProductDiscrepancy')
    ]
