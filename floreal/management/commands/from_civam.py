from django.core.management.base import BaseCommand
import json
from types import SimpleNamespace
from floreal import models as m
import sys


def get_dump(filename):
    print(f" * reading content of {filename}")
    with open(filename) as f:
        dump_list = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
    dump = SimpleNamespace()
    for x in dump_list:
        key = x.model.rsplit(".", 1)[-1]
        val = x.fields
        subkey = x.pk if key != "user" else val.username
        dump.__dict__.setdefault(key, {})[subkey] = val
    return dump


# In [12]: for k, v in dump.__dict__.items():
#     ...:     first_val = list(v.values())[0]
#     ...:     subkeys = list(first_val.__dict__.keys())
#     ...:     print(f"{k}: {', '.join(subkeys)}")


def parse_structure(dump):
    # network: name, auto_validate, description, staff
    # subgroup: name, network, extra_user, auto_validate, staff, users
    # user: password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, groups, user_permissions

    print(" * filtering and creating users")
    USER_FIELDS = "password is_superuser username first_name last_name email is_staff date_joined".split()
    purchaser_usernames = (
        {pc.user[0] for pc in dump.purchase.values()}
        | {u for sg in dump.subgroup.values() for [u] in sg.staff}
        | {u for nw in dump.network.values() for [u] in nw.staff}
        | {u.username for u in dump.user.values() if u.is_staff}
    )
    deleted_usernames = set()
    for u in dump.user.values():
        if not u.is_active or u.username not in purchaser_usernames:
            deleted_usernames.add(u.username)  # Don't bother with people who never bought or left
        else:
            u_db, _ = m.User.objects.get_or_create(
                username=u.username, defaults={k: getattr(u, k) for k in USER_FIELDS}
            )
            u.new_id = u_db.id
    print(f"   removed {len(deleted_usernames)} users out of {len(dump.user)}")

    for p in dump.userphones.values():
        try:
            uid = dump.user[p.user[0]].new_id
            m.FlorealUser.objects.create(user_id=uid, phone=p.phone)
        except KeyError:
            pass
    print("Added phone numbers")

    for old_id, nw in dump.network.items():
        nw_db, _ = m.Network.objects.get_or_create(name=nw.name, defaults={"description": nw.description})
        nw.new_id = nw_db.id
        print(f" * Network {nw.name}")
        for sg in dump.subgroup.values():
            if sg.network != old_id:
                continue
            print(f"   * users")
            for [username] in sg.users:
                if username in deleted_usernames:
                    continue
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id, user_id=dump.user[username].new_id
                )
                mb.is_buyer = True
                mb.save()
            print(f"   * subgroup staff")
            for [username] in sg.staff:
                if username in deleted_usernames:
                    continue
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id, user_id=dump.user[username].new_id
                )
                mb.is_subgroup_staff = True
                mb.save()
        for [username] in nw.staff:
            if username in deleted_usernames:
                continue
            mb, _ = m.NetworkMembership.objects.get_or_create(network_id=nw.new_id, user_id=dump.user[username].new_id)
            mb.is_staff = True
            mb.save()        


def parse_records(dump):
    # delivery: name, network, state, description
    # product: name, delivery, price, quantity_per_package, unit, quantity_limit, unit_weight, quantum, description, place
    # purchase: user, product, quantity
    print(" * deliveries")
    for dv in dump.delivery.values():
        dv_db, _ = m.Delivery.objects.get_or_create(
            name=dv.name,
            network_id=dump.network[dv.network].new_id,
            defaults={"state": dv.state, "description": dv.description},
        )
        dv.new_id = dv_db.id
    print(" * products")
    PRODUCT_FIELDS = "name price quantity_per_package unit quantity_limit unit_weight quantum description place".split()
    n = len(dump.product)
    p = int(n / 100)
    for i, pd in enumerate(dump.product.values()):
        if i % p == 0:
            sys.stdout.write(f"({i}/{n}) ")
            sys.stdout.flush()
        pd_db, _ = m.Product.objects.get_or_create(
            name=pd.name,
            delivery_id=dump.delivery[pd.delivery].new_id,
            defaults={k: getattr(pd, k) for k in PRODUCT_FIELDS},
        )
        pd.new_id = pd_db.id
    print("\n * purchases")
    n = len(dump.purchase)
    p = int(n / 100)
    for i, pc in enumerate(dump.purchase.values()):
        if i % p == 0:
            sys.stdout.write(f"({i}/{n}) ")
            sys.stdout.flush()
        u = dump.user[pc.user[0]]
        if not hasattr(u, "new_id"):
            continue  # deleted user
        pc_db, _ = m.Purchase.objects.get_or_create(
            user_id=u.new_id,
            product_id=dump.product[pc.product].new_id,
            defaults={"quantity": pc.quantity}
        )
        pc.new_id = pc_db.id


class Command(BaseCommand):
    help = "Import legacy data from Civam"

    def add_arguments(self, parser):
        parser.add_argument("input_file", type=str)

    def handle(self, input_file, **kwargs):
        dump = get_dump(input_file)
        parse_structure(dump)
        parse_records(dump)
