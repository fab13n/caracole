import os
os.environ['DJANGO_SETTINGS_MODULE']='solalim.settings'
import sys
sys.path += ["."]

from django import setup
setup()


import json
from floreal.models import *
from collections import defaultdict

FILE_NAME="./floreal-dump-2020-07-21.json"

x = defaultdict(list)

# Sort model elements by model class name
for y in json.load(open(FILE_NAME)): 
    k = y['model'].split(".")[-1] 
    x[k].append(y) 

phones = {  # username -> phone:str
    y['fields']['user'][0]: y['fields']['phone']
    for y in x['userphones']
}

users = { }  # username -> User

# Create missing users
if True:
    user_fields = 'password is_superuser username first_name last_name email is_staff is_active date_joined'.split()
    print("Migrate users")
    for kwargs in x['user']: 
        f = kwargs['fields']
        defaults = {k: f[k] for k in user_fields}
        k = f['username']
        u, created = User.objects.get_or_create(username=k, defaults=defaults)
        print(f" {'-' if created else '+'} {k}") 
        users[k] = u
        phone = phones.get(u.username)
        if phone:
            UserPhone.objects.get_or_create(user=u, defaults={"phone": phone})
else:
    for u in User.objects.all():
        users[u.username] = u

global_staff = set(User.objects.filter(is_staff=True))

floreal = next(nw for nw in x['network'] if nw['fields']['name']=='Floreal')                
nwid = floreal['pk']
nw, created = Network.objects.get_or_create(name='Floreal', defaults={'auto_validate': False})
nw_staff = {User.objects.get(username=y[0]) for y in floreal['fields']['staff']}

if True:
    # Convert floreal subgroups
    print("Floreal subgroups")
    for kwargs in x['subgroup']:
        f = kwargs['fields']
        if f['network'] != nwid:
            continue
        print(f" - {f['name']}")
        xtra = User.objects.get(username=f['extra_user'][0])
        xtra.is_active=False
        xtra.save()
        sg = NetworkSubgroup.objects.create(name=f['name'], network=nw)
        buyers = {users[y[0]] for y in f['users']}
        substaff = {users[y[0]] for y in f['staff']}
        for u in buyers | substaff:
            if not u.is_active:
                continue
            nm = NetworkMembership.objects.create(
                user=u,
                network=nw,
                subgroup=sg,
                is_buyer=u in buyers,
                is_subgroup_staff=u in substaff,
                is_staff=u in global_staff
            )

# Migrate other, mono-group networks
print("Other networks")
for kwargs in x['network']:
    f = kwargs['fields']
    if f['name'] == 'Floreal':
        continue  # Already handled
    nw_id=kwargs['pk']
    nw, created = Network.objects.get_or_create(
        name=f['name'],
        auto_validate=f['auto_validate'],
    )
    if not created:
        continue
    print(f" - {nw.name}")
    (sgf,) = [sg['fields'] for sg in x['subgroup'] if sg['fields']['network'] == nw_id]
    buyers = {users[y[0]] for y in sgf['users']}
    substaff = {users[y[0]] for y in sgf['staff']}
    for u in buyers | substaff | global_staff:
        nm = NetworkMembership.objects.create(
            user=u,
            network=nw,
            is_buyer=u in buyers,
            is_subgroup_staff=u in substaff,
            is_staff=u in global_staff
        )

# Migrate deliveries: put product back together with them
print("Index deliveries")
d = {}  # dv.id -> fields
for dv in x['delivery']: 
    d[dv['pk']] = dict(dv['fields'], products=[])

print(f"Index {len(x['products'])} products within deliveries")
for pd in x['product']: 
    dv = d[pd['fields']['delivery']] 
    dv['products'].append(pd)

products = {}  # old_pd.id -> new_pd.id
     
for y in d.values(): 
    old_nwid = y['network'] 
    nw_name = next(z['fields']['name'] for z in x['network'] if z['pk']==old_nwid)
    nw = Network.objects.get(name=nw_name)

    dv=Delivery.objects.create(
        name=y['name'],
        network=nw,
        state=y['state']
    )
    print(f" - {dv.network.name} / {dv.name}")
    for p in y['products']:
        kwargs = dict(p['fields'], delivery=dv)
        pd = Product.objects.create(**kwargs)
        products[p['pk']] = pd.id

# State REGULATING has been suppressed, so now TERMINATED is E instead of F 
Delivery.objects.filter(state='F').update(state='E')

# Migrate purchases
if True:
    print("Import purchases...")
    for y in x['purchase']:
        f = y['fields']
        Purchase.objects.create(
            user=users[f['user'][0]],
            product_id=products[f['product']], 
            quantity=f['quantity']
        )
