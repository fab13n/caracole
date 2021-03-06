# Generated by Django 3.0.4 on 2020-07-14 05:50

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('floreal', '0022_auto_20200426_1127'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='producer',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='network',
            name='producers',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
    ]
