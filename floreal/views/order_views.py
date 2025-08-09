from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .. import models as m


@login_required()
def orders(request):
    networks = m.Network.objects.filter(
        networkmembership__user=request.user,
        networkmembership__is_buyer=True,
        networkmembership__valid_until=None,
        active=True,
    )
    deliveries = (
        m.Delivery.objects.filter(network__in=networks, state__in="BCD")
        .order_by("distribution_date", "name")
    )
    purchases = (
        m.Purchase.objects.filter(product__delivery__in=deliveries, user=request.user)
        .select_related("product")
    )

    messages = m.AdminMessage.objects.filter(network__in=networks).order_by("id")

    nw_by_id = {}
    dv_by_id = {}
    for nw in networks:
        jnw = {"id": nw.id, "name": nw.name, "slug": nw.slug, "messages": [], "deliveries": []}
        nw_by_id[nw.id] = jnw
    for msg in messages:
        nw_by_id[msg.network_id]["messages"].append(msg.message)
    for dv in deliveries:
        jdv = {
            "id": dv.id,
            "name": dv.name,
            "state": dv.state,
            "state_name": dv.state_name(),
            "purchases": [],
            "total_price": 0.0,
            "freeze": dv.freeze_date,
            "distribution": dv.distribution_date,
        }
        dv_by_id[dv.id] = jdv
        nw_by_id[dv.network_id]["deliveries"].append(jdv)
    for pc in purchases:
        pd = pc.product
        jdv = dv_by_id[pd.delivery_id]
        jpc = {
            "pd_id": pd.id,
            "name": pd.name,
            "unit": pd.unit,
            "quantity": float(pc.quantity),
            "price": float(pc.price),
        }
        jdv["purchases"].append(jpc)
        jdv["total_price"] += float(pc.price)
    active_networks = [jnw for jnw in nw_by_id.values() if jnw["messages"] or jnw["deliveries"]]
    context = {
        "user": request.user,
        "Delivery": m.Delivery,
        "networks": active_networks,
        "general_messages": [msg.message for msg in m.AdminMessage.objects.filter(network=None)],
    }
    return render(request, "orders.html", context)


@login_required()
def order(request):
    vars = {}
    return render(request, "order.html", vars)
