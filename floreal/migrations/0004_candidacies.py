# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('floreal', '0003_subgroup_states'),
    ]

    operations = [
        migrations.CreateModel(
            name='Candidacy',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.TextField(null=True, blank=True)),
                ('subgroup', models.ForeignKey(to='floreal.Subgroup')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='subgroup',
            name='candidates',
            field=models.ManyToManyField(related_name='candidate_of_subgroup', through='floreal.Candidacy', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
