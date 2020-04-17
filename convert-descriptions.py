from floreal.models import Delivery, Product
from markdown import markdown


for q in (Delivery.objects.all(), Product.objects.all()):
    for x in q: 
        if x.description is None or x.description == "": 
            continue 
        x.description=markdown(x.description) 
        x.save()
