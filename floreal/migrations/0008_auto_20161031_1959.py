# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0007_journalentry'),
    ]

    operations = [
        migrations.RenameField(
            model_name='purchase',
            old_name='ordered',
            new_name='quantity',
        ),
        migrations.RemoveField(
            model_name='purchase',
            name='granted',
        ),
        migrations.AlterField(
            model_name='journalentry',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
            preserve_default=True,
        ),
    ]
