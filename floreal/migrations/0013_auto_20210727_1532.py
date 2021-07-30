# Generated by Django 3.2 on 2021-07-27 13:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0012_auto_20210727_1228'),
    ]

    operations = [
        migrations.AddField(
            model_name='florealuser',
            name='latitude',
            field=models.FloatField(default=None, null=True),
        ),
        migrations.AddField(
            model_name='florealuser',
            name='longitude',
            field=models.FloatField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='network',
            name='latitude',
            field=models.FloatField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='network',
            name='longitude',
            field=models.FloatField(default=None, null=True),
        ),
    ]