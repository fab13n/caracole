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
            m.User.objects.filter(user_of_subgroup__network__in=my_networks) |
            m.User.objects.filter(producer_of_network__in=my_networks) |
            m.User.objects.filter(staff_of_network__in=my_networks)
        ).filter(is_active=True)
    # Global staff members can move users across all networks as they see fit.
    # Network staff only move people within (or kick out of) their networks
    # Subgroup staff don't get to this page.

    # id -> {id,first_name, last_name, email, member, nw_staff, sg_staff, producer}
    # member and sg_staff are lists of subgroup ids.
    # nw_staff and producer are lists of network ids
    user_records = { 
        u['id']: dict(u, sg_member=[], nw_staff=[], sg_staff=[], nw_producer=[])
        for u in users.values('id', 'first_name', 'last_name', 'email', 'is_staff')
    }

    network_records = []

    for nw in networks:
        nw_rec = {"id": nw.id, "name": nw.name, "subgroups": []}
        network_records.append(nw_rec)
        subgroups = nw.subgroup_set.all()
        for sg in subgroups:
            nw_rec["subgroups"].append({"id": sg.id, "name": sg.name})
            for u in sg.users.filter(is_active=True).values("id"):
                user_records[u["id"]]["sg_member"].append(sg.id)
            for u in sg.staff.filter(is_active=True).values("id"):
                user_records[u["id"]]["sg_staff"].append(sg.id)
        
        for u in nw.staff.filter(is_active=True).values("id"):
            user_records[u["id"]]["nw_staff"].append(nw.id)
        for u in nw.producers.filter(is_active=True).values("id"):
            user_records[u["id"]]["nw_producer"].append(nw.id)
            
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
    * sg_member: a list of subgroup ids this user should be made member of
    * sg_staff: a list of subgroup ids this user should be made group-staff of
    * nw_staff: a list of network ids  this user should be made staff of
    * nw_producer: a list of network ids  this user should be made producer of
    """

    staff = request.user
    data = json.loads(request.body)
    user = m.User.objects.get(id=data['user'])

    # Get current user status
    old = dict(
        sg_member={u['id'] for u in user.user_of_subgroup.all().values("id")},
        sg_staff={u['id'] for u in user.staff_of_subgroup.all().values("id")},
        nw_staff={u['id'] for u in user.staff_of_network.all().values("id")},
        nw_producer={u['id'] for u in user.producer_of_network.all().values("id")},
        is_staff = user.is_staff
    )

    # Get status goal
    new = dict(
        sg_member=set(data['sg_member']),
        sg_staff=set(data['sg_staff']),
        nw_staff=set(data['nw_staff']),
        nw_producer=set(data['nw_producer']),
        is_staff=data.get('is_staff')
    )

    if not staff.is_staff: # global staff users can do whatever they want
        # Otherwise, staff must be network admin of all the networks and subgroups mentionned
        networks = new['nw_producer'] | new["nw_staff"] | old["nw_producer"] | old["nw_staff"]
        subgroups = new["sg_member"] | new["sg_staff"] | old["sg_member"] | old["sg_staff"]
        networks |= {sg.network_id for sg in m.Subgroup.objects.filter(id__in=subgroups)}
        if any(staff not in nw.staff.all() for nw in networks):
            return HttpResponseForbidden("Not enough admin rights")

    user.user_of_subgroup.set(new["sg_member"])
    user.staff_of_subgroup.set(new["sg_staff"])
    user.staff_of_network.set(new["nw_staff"])
    user.producer_of_network.set(new["nw_producer"])

    print(f"{old['is_staff']=} {new['is_staff']=}")
    if (new['is_staff'] is not None and 
        staff.is_staff and 
        old['is_staff'] != new['is_staff']):
        user.is_staff = new['is_staff']
        user.save()

    m.JournalEntry.log(staff, "Changed u-%d from %s to %s", user.id, old, new)

    # TODO Check that staff user is allowed to make those updates.
    return HttpResponse(b'OK')