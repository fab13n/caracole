# Generated by Django 3.1.4 on 2021-01-01 20:02

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Delivery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(choices=[('A', 'En préparation'), ('B', 'Ouverte'), ('C', 'Admins'), ('D', 'Gelée'), ('E', 'Terminée')], default='A', max_length=1)),
                ('description', models.TextField(blank=True, default=None, null=True)),
            ],
            options={
                'verbose_name_plural': 'Deliveries',
                'ordering': ('-id',),
            },
        ),
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, unique=True)),
                ('auto_validate', models.BooleanField(default=False)),
                ('description', models.TextField(blank=True, default=None, null=True)),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Plural',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singular', models.CharField(max_length=64, unique=True)),
                ('plural', models.CharField(blank=True, default=None, max_length=64, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('price', models.DecimalField(decimal_places=2, max_digits=6)),
                ('quantity_per_package', models.IntegerField(blank=True, null=True)),
                ('unit', models.CharField(blank=True, max_length=256, null=True)),
                ('quantity_limit', models.IntegerField(blank=True, null=True)),
                ('unit_weight', models.DecimalField(blank=True, decimal_places=3, default=0.0, max_digits=6)),
                ('quantum', models.DecimalField(blank=True, decimal_places=2, default=1, max_digits=3)),
                ('description', models.TextField(blank=True, default=None, null=True)),
                ('place', models.PositiveSmallIntegerField(blank=True, default=True, null=True)),
                ('image', models.ImageField(blank=True, default=None, null=True, upload_to='')),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='floreal.delivery')),
            ],
            options={
                'ordering': ('place', '-quantity_per_package', 'name'),
            },
        ),
        migrations.CreateModel(
            name='UserPhone',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(max_length=20)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='NetworkSubgroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='floreal.network')),
            ],
        ),
        migrations.CreateModel(
            name='NetworkMembership',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_staff', models.BooleanField(default=False)),
                ('is_subgroup_staff', models.BooleanField(default=False)),
                ('is_producer', models.BooleanField(default=False)),
                ('is_buyer', models.BooleanField(default=True)),
                ('is_regulator', models.BooleanField(default=False)),
                ('is_candidate', models.BooleanField(default=False)),
                ('network', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='floreal.network')),
                ('subgroup', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='floreal.networksubgroup')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='network',
            name='members',
            field=models.ManyToManyField(related_name='member_of_network', through='floreal.NetworkMembership', to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(default=datetime.datetime.now)),
                ('action', models.CharField(max_length=1024)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='delivery',
            name='network',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='floreal.network'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='producer',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='AdminMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('network', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='floreal.network')),
            ],
        ),
        migrations.CreateModel(
            name='Purchase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=6)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='floreal.product')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('product', 'user')},
            },
        ),
    ]
