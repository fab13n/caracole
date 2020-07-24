import json

from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .. import models as m


def users_html(request):
    return render(request, "users.html", {})


@csrf_exempt
def users_json(request):
    if request.method == 'POST':
        return users_update(request)
    elif request.method == 'GET':
        # TODO add optional per-network restriction in URL
        return users_get(request)
    else:
        return HttpResponseForbidden("Only GET and POST, only by admins")


def users_get(request):
    # TODO add optional per-network restriction in URL
    staff = request.user

    if staff.is_staff:
        # Global staff => access to every user and network
        networks = m.Network.objects.all()
        users = m.User.objects.filter(is_active=True)
    else:
        # Only access to network you are staff of, and their users
        networks = user.staff_of_network.all()
        users = (
            m.User.objects.filter(member_of_network__in=my_networks) |
            m.User.objects.filter(producer_of_network__in=my_networks) |
            m.User.objects.filter(staff_of_network__in=my_networks) |
            m.User.objects.filter(regulator_of_network__in=my_networks)
        ).filter(is_active=True)

    user_records = { 
        u['id']: dict(u, member=[], staff=[], regulator=[], producer=[])
        for u in users.values('id', 'first_name', 'last_name', 'email', 'is_staff')
    }

    network_records = []

    for nw in networks:
        nw_rec = {"id": nw.id, "name": nw.name}
        network_records.append(nw_rec)

        for u in nw.members.filter(is_active=True).values("id"):
            user_records[u["id"]]["member"].append(nw.id)
        for u in nw.staff.filter(is_active=True).values("id"):
            user_records[u["id"]]["staff"].append(nw.id)
        for u in nw.regulators.filter(is_active=True).values("id"):
            user_records[u["id"]]["regulator"].append(nw.id)
        for u in nw.producers.filter(is_active=True).values("id"):
            user_records[u["id"]]["producer"].append(nw.id)
            
    return JsonResponse({
        "is_staff": staff.is_staff,
        "networks": sorted(network_records, key=lambda nw: nw['name']),
        "users": sorted(user_records.values(), key=lambda u: u['last_name'])
        # "users": dict(sorted(user_records.items(), key=lambda pair: pair[1]['last_name']))
    })


def users_update(request):
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
    user = m.User.objects.get(id=data['user'])

    # Get current user status
    old = dict(
        member={u['id'] for u in user.member_of_network.all().values("id")},
        staff={u['id'] for u in user.staff_of_network.all().values("id")},
        roducer={u['id'] for u in user.producer_of_network.all().values("id")},
        regulator={u['id'] for u in user.regulator_of_network.all().values("id")},
        is_staff = user.is_staff
    )

    # Get status goal
    new = dict(
        member=set(data['member']),
        staff=set(data['staff']),
        producer=set(data['producer']),
        regulator=set(data['regulator']),
        is_staff=data.get('is_staff')
    )

    if not staff.is_staff: # global staff users can do whatever they want
        # Otherwise, staff must be network admin of all the networks and subgroups mentionned
        network_ids = new['producer'] | new["staff"] | new["regulator"] |\
                      old["producer"] | old["staff"] | old["regulator"]
        if any(staff not in m.Network.objects.filter(id=nw_id, staff__in=[staff]) for nw_id in networks):
            return HttpResponseForbidden("Not enough admin rights")

    user.staff_of_network.set(new["staff"])
    user.producer_of_network.set(new["producer"])
    user.regulator_of_network.set(new["producer"])

    if (new['is_staff'] is not None and 
        staff.is_staff and 
        old['is_staff'] != new['is_staff']):
        user.is_staff = new['is_staff']
        user.save()

    m.JournalEntry.log(staff, "Changed u-%d from %s to %s", user.id, old, new)

    # TODO Check that staff user is allowed to make those updates.
    return HttpResponse(b'OK')