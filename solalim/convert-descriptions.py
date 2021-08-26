#!/usr/bin/env python
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'solalim.settings'
import django
django.setup()


from floreal.models import Delivery, Product
from markdown import markdown


for q in (Delivery.objects.all(), Product.objects.all()):
    for x in q: 
        if x.description is None or x.description == "": 
            continue
        print(x)
        x.description=markdown(x.description) 
        x.save()
