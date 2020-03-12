# -*- coding: utf-8 -*-


from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='delivery',
            name='state',
            field=models.CharField(default=b'A', max_length=1, choices=[(b'A', 'En pr\xe9paration'), (b'C', 'Admins'), (b'B', 'Ouverte'), (b'E', 'R\xe9gularisation'), (b'D', 'Gel\xe9e'), (b'F', 'Termin\xe9e')]),
            preserve_default=True,
        ),
    ]
