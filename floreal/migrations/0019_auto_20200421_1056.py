# Generated by Django 3.0.4 on 2020-04-21 08:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('floreal', '0018_remove_product_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subgroup',
            name='name',
            field=models.CharField(max_length=256),
        ),
    ]
