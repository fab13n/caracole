import sys
sys.path += ["."]
import os
os.environ['DJANGO_SETTINGS_MODULE']='solalim.settings'
import django
django.setup()
from floreal import models as m
import re


months={
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12}

iregex = r"(\d+)\s*("+"|".join(months.keys())+")"
ciregex = re.compile(iregex, re.IGNORECASE)


def sort_deliveries_par_network_and_date():
    dsets = {}
    for dv in m.Delivery.objects.filter(name__iregex=iregex):
        if not m.Purchase.objects.filter(product__delivery=dv).exists():
            continue
        d, mo = ciregex.search(dv.name).groups()
        ds_id = str(d) + "/" + str(months[mo.lower()])
        k = ds_id + ": " + dv.network.name
        if k not in dsets:
            dsets[k] = []
        dsets[k].append(dv)
    return dsets

def stats_dset(ds):
    users = set()
    ds_total = 0.
    nb_pc = 0
    for dv in ds:
        qpc = list(m.Purchase.objects
                   .filter(product__delivery=dv)
                   .values('product__price', 'quantity', 'user__email'))
        dv_total = sum(x['product__price'] * x['quantity'] for x in qpc)
        ds_total += float(dv_total)
        users |= {x['user__email'] for x in qpc}
        nb_pc += len(qpc)
        print("   * %10.2f€ CA %s" % (dv_total, dv.name))
    print(" *** %10.2f€ CA du jour" % ds_total)
    print(" *** %10.2f€ panier moyens, %d acheteurs" % (
        ds_total / len(users), len(users)
    ))
    return users, ds_total

def stats_all(dsets):
    total = 0
    users = set()
    for name, ds in dsets.items():
        print("\n"+name)
        u, ds_total = stats_dset(ds)
        users |= u
        total += ds_total
    print("\nGrand total:\n --> %10.2f€ Total" % total)
    print(" *** %10.2f€ panier moyens, %d acheteurs" % (total/len(users), len(users)))

if __name__ == "__main__":
    dsets = sort_deliveries_par_network_and_date()
    stats_all(dsets)
