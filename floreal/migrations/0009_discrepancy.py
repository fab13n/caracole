#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0008_granted_ordered_to_quantity'),
    ]

    operations = [
        migrations.CreateModel(
            name='Discrepancy',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('amount', models.DecimalField(max_digits=9, decimal_places=3)),
                ('reason', models.CharField(max_length=256)),
                ('product', models.ForeignKey(to='floreal.Product', on_delete=models.CASCADE)),
                ('subgroup', models.ForeignKey(to='floreal.Subgroup', on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
