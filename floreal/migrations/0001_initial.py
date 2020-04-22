# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Delivery',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(default=b'P', max_length=1, choices=[(b'A', b'Archived'), (b'P', b'Preparation'), (b'C', b'Closed'), (b'O', b'Open'), (b'F', b'Finalized')])),
            ],
            options={
                'ordering': ('-id',),
                'verbose_name_plural': 'Deliveries',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LegacyPassword',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.CharField(max_length=64)),
                ('password', models.CharField(max_length=200)),
                ('circle', models.CharField(max_length=32)),
                ('migrated', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=256)),
                ('staff', models.ManyToManyField(related_name='staff_of_network', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Plural',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('singular', models.CharField(unique=True, max_length=64)),
                ('plural', models.CharField(default=None, max_length=64, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=256)),
                ('price', models.DecimalField(max_digits=6, decimal_places=2)),
                ('quantity_per_package', models.IntegerField(null=True, blank=True)),
                ('unit', models.CharField(max_length=256, null=True, blank=True)),
                ('quantity_limit', models.IntegerField(null=True, blank=True)),
                ('unit_weight', models.DecimalField(default=0.0, max_digits=6, decimal_places=3, blank=True)),
                ('quantum', models.DecimalField(default=1, max_digits=3, decimal_places=2, blank=True)),
                ('delivery', models.ForeignKey(to='floreal.Delivery', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-quantity_per_package', 'name'),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Purchase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ordered', models.DecimalField(max_digits=6, decimal_places=3)),
                ('granted', models.DecimalField(max_digits=6, decimal_places=3)),
                ('product', models.ForeignKey(to='floreal.Product', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Subgroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=256)),
                ('extra_user', models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)),
                ('network', models.ForeignKey(to='floreal.Network', on_delete=models.CASCADE)),
                ('staff', models.ManyToManyField(related_name='staff_of_subgroup', to=settings.AUTH_USER_MODEL)),
                ('users', models.ManyToManyField(related_name='user_of_subgroup', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='subgroup',
            unique_together=set([('network', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='purchase',
            unique_together=set([('product', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='product',
            unique_together=set([('delivery', 'name')]),
        ),
        migrations.AddField(
            model_name='delivery',
            name='network',
            field=models.ForeignKey(to='floreal.Network', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='delivery',
            unique_together=set([('network', 'name')]),
        ),
    ]
