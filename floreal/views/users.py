import json
import io

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .. import models as m

KEYS = ("buyer", "staff", "producer", "regulator")


def users_html(request):
    return render(request, "users.html", {})


@csrf_exempt
def users_json(request):
    if (
        not request.user.is_staff
        and not m.NetworkMembership.objects.filter(
            user=request.user, is_staff=True
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
    # TODO add optional per-network restriction in URL
    staff = request.user

    if staff.is_staff:
        # Global staff => access to every user and network
        networks = m.Network.objects.all()
        users = m.User.objects.filter(is_active=True)
    else:
        # Only access to network you are staff of, and their users
        networks = staff.staff_of_network.all()
        users = m.User.objects.filter(member_of_network__in=networks).filter(
            is_active=True
        )

    user_records = {
        u_rec["id"]: dict(**u_rec, **{k: [] for k in KEYS})
        for u_rec in users.values("id", "first_name", "last_name", "email", "is_staff", "florealuser__description", "florealuser__image_description")
    }

    # Convert image URLs
    for u in user_records.values():
        url = u['florealuser__image_description']
        u['florealuser__image_description'] = {'url': settings.MEDIA_URL + url} if url else None

    network_records = []

    for nw in networks:
        nw_rec = {"id": nw.id, "name": nw.name}
        network_records.append(nw_rec)
        for nm in m.NetworkMembership.objects.filter(network=nw):
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
            "users": sorted(user_records.values(), key=lambda u: u["last_name"])
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

    # TODO retrieve set of considered networks.
    # TODO check rights against each of these networks
    # TODO or consider that every network has been listed in th UI?

    network_ids = data["networks"]

    if staff.is_staff:
        pass
    elif all(
        m.NetworkMembership.objects.filter(
            user=staff, is_staff=True, newtork_id=nw_id
        ).exists()
        for nw_id in network_ids
    ):
        pass
    else:
        return HttpResponseForbidden("Not enough rights")

    if user.is_staff != data["is_staff"]:
        user.is_staff = data["is_staff"]
        user.save()

    descr = data["florealuser__description"]
    if user.florealuser is None:
        m.FlorealUser.objects.create(user=user, description=descr)
        user.refresh_from_db()

    if user.florealuser.description != descr:
        user.florealuser.description = descr
        user.florealuser.save()

    # handle image_description
    if 'florealuser__image_description' in data:
        img = data['florealuser__image_description']
        content = img['content'].encode('latin1')
        reader = io.BytesIO(content)
        user.florealuser.image_description.save(img['name'], reader)
        user.florealuser.save()

    for nw_id in network_ids:
        (nm, created) = m.NetworkMembership.objects.get_or_create(
            user=user, network_id=nw_id, defaults={"is_" + key: False for key in KEYS}
        )
        must_save = False
        must_delete = True
        for key in KEYS:
            attr = "is_" + key
            old_val = getattr(nm, attr)
            new_val = nw_id in data[key]
            if new_val:
                must_delete = False
            if old_val != new_val:
                setattr(nm, attr, new_val)
                must_save = True
        if must_delete:
            nm.delete()
        elif must_save:
            nm.save()

    m.JournalEntry.log(staff, "Edited user u-%d", user.id)

    return HttpResponse(b"OK")
