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
        subkey = x.pk
        dump.__dict__.setdefault(key, {})[subkey] = val
    return dump


# In [12]: for k, v in dump.__dict__.items():
#     ...:     first_val = list(v.values())[0]
#     ...:     subkeys = list(first_val.__dict__.keys())
#     ...:     print(f"{k}: {', '.join(subkeys)}")


def parse_u(dump):
    # user: password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, groups, user_permissions

    print(" * filtering and creating users")
    USER_FIELDS = "password is_superuser username first_name last_name email is_staff date_joined".split()
    purchaser_user_ids = {pc.user for pc in dump.purchase.values()}
    staff_user_ids = (
        {u for sg in dump.subgroup.values() for u in sg.staff}
        | {u for nw in dump.network.values() for u in nw.staff}
        | {k for k, v in dump.user.items() if v.is_staff}
    )
    candidate_user_ids = {cd.user for cd in dump.candidacy.values()}
    kept_user_ids = purchaser_user_ids | staff_user_ids | candidate_user_ids
    deleted_user_ids = set()
    for uid, u in dump.user.items():
        if not u.is_active or uid not in kept_user_ids:
            deleted_user_ids.add(
                uid
            )  # Don't bother with people who never bought or left
        else:
            u_db, _ = m.User.objects.get_or_create(
                username=u.username, defaults={k: getattr(u, k) for k in USER_FIELDS}
            )
            u.new_id = u_db.id
    print(f"   removed {len(deleted_user_ids)} users out of {len(dump.user)}")
    assert all(k not in kept_user_ids or k in deleted_user_ids or v.new_id for k, v in dump.user.items())
    # assert all(id not in kept_user_ids for id in deleted_user_ids)
    # assert all(id not in deleted_user_ids for id in kept_user_ids)

    for p in dump.userphones.values():
        try:
            new_uid = dump.user[p.user].new_id
            m.FlorealUser.objects.create(user_id=new_uid, phone=p.phone)
        except AttributeError:
            pass
    print(" * Added phone numbers")


def parse_nw(dump):
    # network: name, auto_validate, description, staff
    # subgroup: name, network, extra_user, auto_validate, staff, users
    for old_nwid, nw in dump.network.items():
        new_nw, _ = m.Network.objects.get_or_create(name=nw.name)
        nw.new_id = new_nw.id
        print(f" * Network {nw.name}")
        subgroups = [sg for sg in dump.subgroup.values() if sg.network == old_nwid]
        single_subgroup = len(subgroups) == 1
        for sg in dump.subgroup.values():
            if sg.network != old_nwid:
                continue
            print(f"   * subgroup {sg.name}")
            if single_subgroup:
                new_sg_id = None
            else:
                sg_db, _ = m.NetworkSubgroup.objects.get_or_create(
                    network_id=nw.new_id, name=sg.name
                )
                new_sg_id = sg_db.id
                sg.new_id = new_sg_id
            print(f"     * users")
            for old_uid in sg.users:
                u = dump.user[old_uid]
                if not hasattr(u, "new_id"):
                    continue  # deleted user
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id,
                    user_id=u.new_id,
                    defaults={"subgroup_id": new_sg_id},
                )
                mb.is_buyer = True
                mb.save()
            print(f"     * subgroup staff")
            for old_uid in sg.staff:
                u = dump.user[old_uid]
                if not hasattr(u, "new_id"):
                    continue  # deleted user
                mb, _ = m.NetworkMembership.objects.get_or_create(
                    network_id=nw.new_id,
                    user_id=u.new_id,
                    defaults={"subgroup_id": new_sg_id},
                )
                mb.is_subgroup_staff = True
                mb.save()

        print(f"     * network staff")
        for old_uid in nw.staff:
            u = dump.user[old_uid]
            if not hasattr(u, "new_id"):
                continue  # deleted user
            mb, _ = m.NetworkMembership.objects.get_or_create(
                network_id=nw.new_id, user_id=u.new_id
            )
            mb.is_staff = True
            mb.save()


def parse_dv(dump):
    # delivery: name, network, state, description
    # product: name, delivery, price, quantity_per_package, unit, quantity_limit, unit_weight, quantum, description, place
    print(" * deliveries")
    CONVERT_STATE = {k: v for k, v in "AA BB CC DD FE".split()}
    for dv in dump.delivery.values():
        dv_db, _ = m.Delivery.objects.get_or_create(
            name=dv.name,
            network_id=dump.network[dv.network].new_id,
            defaults={"state": CONVERT_STATE[dv.state], "description": dv.description},
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
    print(" Done")


def parse_pc(dump):
    # purchase: user, product, quantity
    print("\n * purchases")
    n = len(dump.purchase)
    p = int(n / 100)
    for i, pc in enumerate(dump.purchase.values()):
        if i % p == 0:
            sys.stdout.write(f"({i}/{n}) ")
            sys.stdout.flush()
        u = dump.user[pc.user]
        if not hasattr(u, "new_id"):
            continue  # deleted user
        pc_db, _ = m.Purchase.objects.get_or_create(
            user_id=u.new_id,
            product_id=dump.product[pc.product].new_id,
            defaults={"quantity": pc.quantity},
        )
        pc.new_id = pc_db.id
    print(" Done")

def parse_cd(dump):
    print(f" * candidacies")
    for cd in dump.candidacy.values():
        u = dump.user[cd.user]
        if not hasattr(u, "new_id"):
            continue  # deleted user
        sg = dump.subgroup[cd.subgroup]
        new_nw_id = dump.network[sg.network].new_id
        nm, _ = m.NetworkMembership.objects.get_or_create(
            network_id=new_nw_id, user_id=u.new_id, defaults={"is_buyer": False}
        )
        nm.is_candidate = True
        nm.save()


class Command(BaseCommand):
    help = "Import legacy data from Civam"

    def add_arguments(self, parser):
        parser.add_argument("input_file", type=str)

    def handle(self, input_file, **kwargs):
        dump = get_dump(input_file)
        parse_u(dump)
        parse_nw(dump)
        parse_dv(dump)
        parse_pc(dump)
        parse_cd(dump)
