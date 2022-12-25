from django.core.management.base import BaseCommand
import json
from types import SimpleNamespace
from floreal import models as m
import sys
from markdown import markdown
from django.db import IntegrityError, DataError

def get_dump(filename):
    print(f" * reading content of {filename}")
    with open(filename) as f:
        dump_list = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
    dump = SimpleNamespace()
    for x in dump_list:
        key = x.model.rsplit(".", 1)[-1]
        val = x.fields
        subkey = x.pk
        dump.__dict__.setdefault(key, {})[subkey] = val
    return dump


# In [12]: for k, v in dump.__dict__.items():
#     ...:     first_val = list(v.values())[0]
#     ...:     subkeys = list(first_val.__dict__.keys())
#     ...:     print(f"{k}: {', '.join(subkeys)}")


def parse_structure(dump, kept_networks):
    # network: name, auto_validate, description, staff
    # subgroup: name, network, extra_user, auto_validate, staff, users
    # user: password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, groups, user_permissions

    print(" * filtering and creating users")
    USER_FIELDS = "password is_superuser username first_name last_name email is_staff date_joined".split()
    purchaser_user_ids = {pc.user for pc in dump.purchase.values()}
    staff_user_ids = (
        {u for sg in dump.subgroup.values() for u in sg.staff}
        | {u for nw in dump.network.values() for u in nw.staff}
        | {k for k, v in dump.user.items() if v.is_staff}
    )
    kept_user_ids = purchaser_user_ids | staff_user_ids
    deleted_user_ids = set()
    creation_count = 0
    for uid, u in dump.user.items():
        if not u.is_active or uid not in kept_user_ids:
            deleted_user_ids.add(uid)  # Don't bother with people who never bought or left
            u.new_id = None
        else:
            u_db, created = m.User.objects.get_or_create(
                username=u.username, defaults={k: getattr(u, k) for k in USER_FIELDS}
            )
            if created:
                creation_count += 1
            u.new_id = u_db.id
    print(f"   * disregarded {len(deleted_user_ids)} users out of {len(dump.user)}")
    print(f"   * created {creation_count} new user profiles")

    for p in dump.userphones.values():
        try:
            new_uid = dump.user[p.user].new_id
            m.FlorealUser.objects.create(user_id=new_uid, phone=p.phone)
        except (KeyError, AttributeError):
            pass  # uid does not exist
        except IntegrityError:
            pass  # FlorealUser already exists
        except DataError:
            print(f"   WARNING: invalid phone number for {dump.user[p.user].email}: {repr(p.phone)}")
    print(" * Added phone numbers")

    for old_nwid, nw in dump.network.items():
        if kept_networks is not None and nw.name not in kept_networks:
            print(f" * (Network {nw.name} skipped)")
            nw.new_id = None
            continue
        nw_db, _ = m.Network.objects.get_or_create(name=nw.name)
        nw.new_id = nw_db.id
        print(f" * Network {nw.name}")
        subgroups = [sg for sg in dump.subgroup.values() if sg.network == old_nwid]
        single_subgroup = len(subgroups) == 1
        for sg in subgroups:
            if single_subgroup:
                print("   * (no subgroup)")
                new_sg_id = None
            else:
                print(f"   * subgroup {sg.name}")
                sg_db, _ = m.NetworkSubgroup.objects.get_or_create(network_id=nw.new_id, name=sg.name)
                new_sg_id = sg_db.id
            print(f"     * users")
            for old_uid in sg.users:
                if old_uid in deleted_user_ids:
                    continue
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id, user_id=dump.user[old_uid].new_id, valid_until=None, defaults={"subgroup_id": new_sg_id}
                )
                mb.is_buyer = True
                mb.save()
            print(f"     * subgroup staff")
            for old_uid in sg.staff:
                if old_uid in deleted_user_ids:
                    continue
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id, user_id=dump.user[old_uid].new_id, valid_until=None, defaults={"subgroup_id": new_sg_id}
                )
                mb.is_subgroup_staff = True
                mb.save()
        for old_uid in nw.staff:
            if old_uid in deleted_user_ids:
                continue
            mb, _ = m.NetworkMembership.objects.get_or_create(network_id=nw.new_id, user_id=dump.user[old_uid].new_id, valid_until=None)
            mb.is_staff = True
            mb.save()


def parse_records(dump, kept_networks):
    # delivery: name, network, state, description
    # product: name, delivery, price, quantity_per_package, unit, quantity_limit, unit_weight, quantum, description, place
    # purchase: user, product, quantity
    print(" * deliveries")
    CONVERT_STATE = {k: v for k, v in "AA BB CC DD ED FE".split()}
    for dv in dump.delivery.values():
        network_id=dump.network[dv.network].new_id
        if network_id is None:
            dv.new_id = None
            continue
        dv_db, _ = m.Delivery.objects.get_or_create(
            name=dv.name,
            network_id=network_id,
            defaults={"state": CONVERT_STATE[dv.state], "description": markdown(dv.description or "")},
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
        delivery_id=dump.delivery[pd.delivery].new_id
        if delivery_id is None:
            pd.new_id = None
            continue
        pd_db, _ = m.Product.objects.get_or_create(
            name=pd.name,
            delivery_id=delivery_id,
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
        u = dump.user[pc.user]
        product_id = dump.product[pc.product].new_id
        if u.new_id is None or product_id is None:
            pc.new_id = None
            continue
        pc_db, _ = m.Purchase.objects.get_or_create(
            user_id=u.new_id,
            product_id=product_id,
            defaults={"quantity": pc.quantity}
        )
        pc.new_id = pc_db.id


class Command(BaseCommand):
    help = "Import legacy data from Caracole"

    def add_arguments(self, parser):
        parser.add_argument("input_file", type=str)
        parser.add_argument("-n", "--networks", type=str, help="Comma-separated list of networks to import")

    def handle(self, input_file, **kwargs):
        kept_networks = [n.strip() for n in kwargs["networks"].split(",")] if kwargs["networks"] else None
        dump = get_dump(input_file)
        parse_structure(dump, kept_networks)
        parse_records(dump, kept_networks)
