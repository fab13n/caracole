# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0004_candidacies'),
    ]

    operations = [
        migrations.DeleteModel(
            name='LegacyPassword',
        ),
        migrations.AddField(
            model_name='network',
            name='auto_validate',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='subgroup',
            name='auto_validate',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
