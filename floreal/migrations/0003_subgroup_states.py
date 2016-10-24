# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0002_rename_states'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubgroupStateForDelivery',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', models.CharField(default=b'X', max_length=1, choices=[(b'Y', 'Commande valid\xe9e'), (b'X', 'Non valid\xe9'), (b'Z', 'Compta valid\xe9e')])),
                ('delivery', models.ForeignKey(to='floreal.Delivery')),
                ('subgroup', models.ForeignKey(to='floreal.Subgroup')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='state',
            field=models.CharField(default=b'A', max_length=1, choices=[(b'A', 'En pr\xe9paration'), (b'C', 'Admins'), (b'B', 'Ouverte'), (b'E', 'R\xe9gularisation'), (b'D', 'Gel\xe9e'), (b'F', 'Termin\xe9e')]),
            preserve_default=True,
        ),
    ]
