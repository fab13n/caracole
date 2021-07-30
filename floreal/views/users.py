import io
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .. import models as m

KEYS = ("buyer", "staff", "producer", "regulator")


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
        return user_update(request)
    elif request.method == "GET":
        # TODO add optional per-network restriction in URL
        return users_get(request)
    else:
        return HttpResponseForbidden("Only GET and POST")


def users_get(request):
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
        u_rec["id"]: dict(**u_rec, **{k: [] for k in KEYS})
        for u_rec in users.values(
            "id",
            "first_name",
            "last_name",
            "email",
            "is_staff",
            "florealuser__description",
            "florealuser__image_description",
            "florealuser__latitude",
            "florealuser__longitude",
            "florealuser__phone",
        )
    }

    # Convert image URLs
    for u in user_records.values():
        url = u["florealuser__image_description"]
        u["florealuser__image_description"] = (
            {"url": settings.MEDIA_URL + url} if url else None
        )

    network_records = []

    for nw in networks:
        nw_rec = {"id": nw.id, "name": nw.name}
        network_records.append(nw_rec)
        # TODO perform in a single .filter(network__in=networks, valid_until=None) request
        for nm in m.NetworkMembership.objects.filter(network=nw, valid_until=None):
            u_rec = user_records.get(nm.user_id)
            if u_rec is None:
                continue  # Inactive. Membership should be deleted
            for key in KEYS:
                if getattr(nm, "is_" + key):
                    u_rec[key].append(nw.id)

    return JsonResponse(
        {
            "is_staff": staff.is_staff,
            "networks": sorted(network_records, key=lambda nw: nw["name"]),
            "users": sorted(user_records.values(), key=lambda u: u["last_name"]),
        }
    )


def user_update(request):
    """
    The incoming JSON answer to be parsed is an object with fields:

    * user: a user id
    * is_staff: should the user be made a global staff?
    * member: a list of network ids this user should be made member of
    * staff: a list of network ids  this user should be made staff of
    * producer: a list of network ids  this user should be made producer of
    """

    staff = request.user
    data = json.loads(request.body)
    user = m.User.objects.get(id=data["user"])

    network_ids = data["networks"]

    if staff.is_staff:
        pass
    elif all(
        m.NetworkMembership.objects.filter(
            user=staff, is_staff=True, network_id=nw_id, valid_until=False
        ).exists()
        for nw_id in network_ids
    ):
        pass
    else:
        return HttpResponseForbidden("Not enough rights")

    if user.is_staff != data["is_staff"]:
        # TODO: prevent global staff from removing their own privilege?
        user.is_staff = data["is_staff"]
        user.save()

    fu = user.florealuser
    if fu is None:
        fu = m.FlorealUser.objects.create(user=user)
        user.refresh_from_db()

    fu.latitude = float(data["florealuser__latitude"])
    fu.longitude = float(data["florealuser__longitude"])
    fu.phone = data["florealuser__phone"]
    fu.description = data["florealuser__description"]

    # handle image_description
    img = data.get("florealuser__image_description")
    if img is not None:
        img = data["florealuser__image_description"]
        content = img["content"].encode("latin1")
        reader = io.BytesIO(content)
        fu.image_description.save(img["name"], reader)

    fu.save()

    for nw_id in network_ids:

        # TODO: get all memberships in a single request
        # .filter(user=user, valid_until=None, network_id__in=network_ids)

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

        for key in KEYS:
            attr = "is_" + key
            old_val = getattr(old_nm, attr, False)
            new_val = nw_id in data[key]
            if old_val != new_val:
                setattr(new_nm, attr, new_val)
                some_fields_changed = True
            if new_val:
                some_fields_true = True

        if some_fields_changed:
            old_nm.valid_until = m.Now()
            old_nm.save()
            if some_fields_true:
                new_nm.save()

    m.JournalEntry.log(staff, "Edited user u-%d", user.id)

    return HttpResponse(b"OK")
