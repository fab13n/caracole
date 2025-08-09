import io
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Max, Count

from .. import models as m

BOOL_KEYS = ("buyer", "staff", "subgroup_staff", "producer")


def users_html(request):
    return render(request, "users.html", {})


@csrf_exempt
def users_json(request):
    if (
        not request.user.is_staff
        and not m.NetworkMembership.objects.filter(
            user=request.user, is_staff=True, valid_until=None
        ).exists()
    ):
        return HttpResponseForbidden("Admins only")
    elif request.method == "POST":
        return _user_update(request)
    elif request.method == "GET":
        # TODO add optional per-network restriction in URL
        return _users_get(request)
    else:
        return HttpResponseForbidden("Only GET and POST")


def _users_get(request):
    staff = request.user

    if staff.is_staff:
        # Global staff => access to every user and network
        networks = m.Network.objects.all()
        users = m.User.objects.filter(is_active=True)
    else:
        # Only access to network you are staff of, and their users
        networks = m.Network.objects.filter(
            networkmembership__user=staff,
            networkmembership__is_staff=True,
            networkmembership__valid_until=None,
        )
        users = m.User.objects.filter(
            networkmembership__network__in=networks, is_active=True
        )

    user_records = {
        u_rec["id"]: dict(**u_rec, **{k: [] for k in BOOL_KEYS}, subgroups={})
        for u_rec in users.values(
            "id",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            # "florealuser__description",
            # "florealuser__image_description",
            # "florealuser__latitude",
            # "florealuser__longitude",
            "florealuser__phone",
        )
    }

    # # Convert image URLs
    # for u in user_records.values():
    #     url = u["florealuser__image_description"]
    #     u["florealuser__image_description"] = (
    #         {"url": settings.MEDIA_URL + url} if url else None
    #     )

    network_records = []

    for nw in networks:
        nw_rec = {"id": nw.id, "name": nw.name}
        network_records.append(nw_rec)
        # TODO perform in a single .filter(network__in=networks, valid_until=None) request
        for nm in m.NetworkMembership.objects.filter(network=nw, valid_until=None):
            u_rec = user_records.get(nm.user_id)
            if u_rec is None:
                continue  # Inactive. Membership should be deleted
            for key in BOOL_KEYS:
                if getattr(nm, "is_" + key):
                    u_rec[key].append(nw.id)
            if (sg_id := nm.subgroup_id) is not None:
                u_rec['subgroups'][nw.id] = sg_id
        nw_rec['subgroups'] = list(nw.networksubgroup_set.all().values("id", "name")) or None

    return JsonResponse(
        {
            "is_staff": staff.is_staff,
            "networks": sorted(network_records, key=lambda nw: nw["name"]),
            "users": sorted(user_records.values(), key=lambda u: u["last_name"]),
        }
    )


def _user_update(request):
    """
    The incoming JSON answer to be parsed is an object with fields:

    * user: a user id
    * is_staff: should the user be made a global staff?
    * member: a list of network ids this user should be made member of
    * staff: a list of network ids this user should be made staff of
    * subgroup_staff: a list of network ids in which this user should be their subgroup's id.
    * producer: a list of network ids  this user should be made producer of
    """

    staff = request.user
    data = json.loads(request.body)
    user = m.User.objects.get(id=data["user"])

    network_ids = data["networks"]

    # Check permissions
    if staff.is_staff:
        pass
    elif all(
        m.NetworkMembership.objects.filter(
            user=staff, is_staff=True, network_id=nw_id, valid_until=None
        ).exists()
        for nw_id in network_ids
    ):
        # Requesting user is staff of every network.
        # TODO: single request by asking all of the network they staff
        # then checking for set inclusion in Python
        pass
    else:
        return HttpResponseForbidden("Not enough rights")

    if user.is_staff != (new_staff_status := data.get("is_staff", False)):
        # TODO: prevent global staff from removing their own privilege?
        if not staff.is_staff:
            # Only global staff can change global staff status of others
            return HttpResponseForbidden("Not enough rights")
        user.is_staff = new_staff_status
        user.save()

    if staff.is_staff:
        # Only global staff is allowed to change user identity
        user.florealuser.phone = data["florealuser__phone"]
        user.florealuser.save()
        user.email = user.username = data["email"]
        user.first_name = data["first_name"]
        user.last_name = data["last_name"]
        user.save()

    for nw_id in network_ids:

        # TODO: get all memberships in a single request
        # .filter(user=user, valid_until=None, network_id__in=network_ids)
        # out of the loop, then retrieve the matching network in each loop iteration.

        old_nm = m.NetworkMembership.objects.filter(
            user=user,
            network_id=nw_id,
            valid_until=None,
        ).first()

        # Object created with the direct constructor, not with .objects.create().
        # As a result it isn't inserted in DB right now. It will be inserted only
        new_nm = m.NetworkMembership(user=user, network_id=nw_id, is_buyer=False)

        some_fields_changed = False
        some_fields_true = False

        for key in BOOL_KEYS:
            attr = "is_" + key
            old_val = getattr(old_nm, attr, False)
            new_val = nw_id in data[key]
            if bool(old_val) != bool(new_val):
                some_fields_changed = True
            if new_val:
                some_fields_true = True
            if nw_id == 27:
                print(f"Set {key} to {attr} = {new_val}")
            setattr(new_nm, attr, new_val)

        # TODO: would be nice to check that is_subgroup_staff is only enabled for nw with subgroups
        # TODO: check that subgroup presence in nw and nm match.

        # Subgroup id isn't a boolean flag, has to be handled differently.
        new_sg_id = data["subgroups"].get(str(nw_id))
        if new_sg_id and (old_nm is None or int(new_sg_id) != old_nm.subgroup_id):
            some_fields_changed = some_fields_true = True
            assert m.NetworkSubgroup.objects.get(pk=new_sg_id).network_id == nw_id
            new_nm.subgroup_id = new_sg_id

        if some_fields_changed:
            if old_nm is not None:
                old_nm.valid_until = m.Now()
                old_nm.save()
            if some_fields_true:
                new_nm.save()

    m.JournalEntry.log(staff, "Edited user u-%d", user.id)

    return HttpResponse(b"OK")


@login_required()
def user(request):
    vars = {
        "bestof": m.Bestof.objects.filter(user=request.user).first(),
        "agg": m.Bestof.objects.aggregate(Sum("total"), Max("total"), Count("total")),
    }
    return render(request, "user.html", vars)
