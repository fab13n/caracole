#!/usr/bin/python3

"""Helpers to edit products list: generate suggestions based on current and
past products, parse POSTed forms to update a delivery's products list."""

import django
from django import forms
from django.shortcuts import render, redirect
from django.template.context_processors import csrf
from django.http import HttpResponseForbidden
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

from .getters import get_delivery
from .decorators import nw_admin_required
from ..models import Product, Delivery, JournalEntry
from ..penury import set_limit
from django.http import JsonResponse


IMAGE_SIZE = 250


def _serialize_product(pd):
    return { 
        'id': pd.id,
        'name': pd.name,
        'price': float(pd.price),
        'unit': pd.unit,
        'quantity_limit': pd.quantity_limit,
        'quantity_per_package': pd.quantity_per_package,
        'quantum': float(pd.quantum),
        'unit_weight': float(pd.unit_weight),
        'description': pd.description,
        'delivery': pd.delivery_id,
        'image': pd.image.url if pd.image else None
    }

def delivery_products_json(request, delivery):
    dv = get_delivery(delivery)
    return JsonResponse({
        'id': dv.id,
        'name': dv.name,
        'state': dv.state,
        'description': dv.description,
        'products': [_serialize_product(pd) for pd in dv.product_set.all()]
    })

@nw_admin_required(lambda a: get_delivery(a['delivery']).network)
def edit_delivery_products(request, delivery):
    """Edit a delivery (name, state, products). Network staff only."""

    delivery = get_delivery(delivery)

    if request.user not in delivery.network.staff.all():
        return HttpResponseForbidden('Réservé aux administrateurs du réseau '+delivery.network.name)

    if request.method == 'POST':  # Handle submitted data
        _parse_form(request)
        JournalEntry.log(request.user, "Edited products for delivery dv-%d %s/%s", delivery.id, delivery.network.name, delivery.name)
        if 'save_and_leave' in request.POST:
            return redirect('edit_delivery', delivery.id)
        else:
            return redirect('edit_delivery_products', delivery.id)

    else:  # Create and populate forms to render
        vars = {'user': request.user, 'delivery': delivery}
        vars.update(csrf(request))
        return render(request,'edit_delivery_products.html', vars)


def _get_pd_fields(d, files, r_prefix):
    """Retrieve form fields representing a product."""
    fields = ['id', 'name', 'price', 'quantity_per_package', 'unit', 'quantity_limit', 'quantum', 'unit_weight',
              'place', 'described', 'description', 'image-modified']
    raw = {f: d.get("%s-%s" % (r_prefix, f), None) for f in fields}
    id = raw['id']
    id = int(id) if id and id.isdigit() else None
    if not raw['name']:
        return {'id': id, 'deleted': True}  # All fields empty means deleted
    qpp = raw['quantity_per_package']
    quota = raw['quantity_limit']
    quantum = raw['quantum']
    weight = raw['unit_weight']
    # TODO This is the place to apply some unit names normalisation.
    if not weight:  # 0 or None
        weight = 1 if raw['unit'] == 'kg' else 0
    r = {'id': id,
         'name': raw['name'],
         'place': int(raw['place']),
         'price': float(raw['price']),
         'quantity_per_package': int(qpp) if qpp else None,
         'unit': raw['unit'] or 'pièce',
         'quantity_limit': int(quota) if quota else None,
         'quantum': float(quantum) if quantum else None,
         'unit_weight': float(weight) if weight is not None else None,
         'description': raw['description'] if raw['described'] else None,
         'deleted': "%s-deleted" % (r_prefix) in d,
    }
    if raw['image-modified'] == "1":
        r['image'] = files.get("%s-image-upload" % r_prefix)
    return r


def _pd_update(pd, fields):
    """Update a model object according to form fields."""
    pd.name = fields['name']
    pd.place = fields['place']
    pd.price = fields['price']
    pd.quantity_per_package = fields['quantity_per_package']
    pd.unit = fields['unit']
    pd.quantity_limit = fields['quantity_limit']
    pd.unit_weight = fields['unit_weight']
    pd.quantum = fields['quantum']
    pd.description = fields['description']
    if 'image' in fields:
        pd.image = fields['image'] 
        _convert_image(pd)


def _convert_image(pd):
    f = pd.image.file
    image = Image.open(f)
    w = image.width
    h = image.height
    if w > h:
        (x, y, w) = ((w-h)/2, 0, h)
    else:
        (x, y, h) = (0, (h-w)/2, w)
    image = image.crop((x, y, w+x, h+y))
    image = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.ANTIALIAS)
    image = image.convert('RGB')  # In case of CMYK or RGBA
    name = "pd_"+str(pd.id)+".jpg"
    buffer = BytesIO()
    image.save(buffer, "JPEG")
    in_memory_file = InMemoryUploadedFile(buffer, f.field_name, name, f.content_type, None, f.charset)
    pd.image.file = in_memory_file
    pd.image.name = name


def _parse_form(request):
    """Parse a delivery edition form and update DB accordingly."""
    d = request.POST
    dv = Delivery.objects.get(pk=int(d['dv-id']))

    # Edit delivery name and state
    dv.name = d['dv-name']
    dv.state = d['dv-state']
    descr = d['dv-description'].strip()
    dv.description = descr or None
    dv.save()

    for r in range(int(d['n_rows'])):
        fields = _get_pd_fields(d, request.FILES, 'r%d' % r)
        if fields.get('id'):
            pd = Product.objects.get(pk=fields['id'])
            if pd.delivery == dv:
                if fields['deleted']:  # Delete previously existing product
                    #print("Deleting product",  pd)
                    pd.delete()
                    # Since purchases have foreign keys to purchased products,
                    # they will be automatically deleted.
                    # No need to update penury management either, as there's
                    # no purchase of this product left to adjust.
                else:  # Update product
                    # print("Updating product", pd)
                    _pd_update(pd, fields)
                    pd.save(force_update=True)
            else:  # From another delivery
                if fields['deleted']:  # Don't import product
                    # print("Ignoring past product", pd)
                    pass
                else:  # Import product copy from other delivery
                    # print("Importing past product",  pd)
                    _pd_update(pd, fields)
                    pd.delivery = dv
                    pd.id = None
                    pd.save(force_insert=True)
        elif fields['deleted']:
                # print("New product in r%d deleted/empty: ignoring" % r)
                pass
        else:  # Parse products created from blank lines
            # print("Adding new product from line #%d" % r)
            pd = Product.objects.create(name=fields['name'],
                                        description=fields['description'],
                                        price=fields['price'],
                                        place=fields['place'],
                                        quantity_per_package=fields['quantity_per_package'],
                                        quantity_limit=fields['quantity_limit'],
                                        unit=fields['unit'],
                                        unit_weight=fields['unit_weight'],
                                        delivery=dv,
                                        image=fields.get('image'))
            pd.save()

    # In case of change in quantity limitations, adjust granted quantities for purchases
    for pd in dv.product_set.all():
        set_limit(pd)
