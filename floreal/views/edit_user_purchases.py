from django.shortcuts import redirect, render_to_response
from django.core.context_processors import csrf

from .. import models as m
from ..penury import set_limit

def edit_user_purchases(request, delivery):
    """Let user order for himself, or modified an order on an open delivery."""
    delivery = m.Delivery.objects.get(id=delivery)
    user = request.user
    order = m.Order(user, delivery)
    if request.method == 'POST':
        if _parse_form(request):
            return redirect("index")
        else:
            # TODO: display errors in template
            return redirect("edit_user_purchases", delivery=delivery.id)
    else:
        vars = {
            'user': user,
            'delivery': delivery,
            'subgroup': delivery.network.subgroup_set.get(staff__in=[user]),
            'products': m.Product.objects.filter(delivery=delivery),
            'purchases': order.purchases
        }
        vars.update(csrf(request))
        return render_to_response('edit_user_purchases.html', vars)


def _parse_form(request):
    """
    Parse responses from user purchases.
    :param request:
    :return:
    """
    d = request.POST
    dv = m.Delivery.objects.get(pk=int(d['dv-id']))
    od = m.Order(request.user, dv)
    prev_purchases = {pc.product: pc for pc in od.purchases}
    for pd in dv.product_set.all():
        ordered = float(d["pd%s" % pd.id])
        if ordered <= 0:
            continue
        if pd in prev_purchases:
            pc = prev_purchases[pd]
        else:
            pc = m.Purchase.objects.create(user=request.user, product=pd, ordered=0, granted=0)
        pc.ordered = ordered
        pc.granted = ordered
        pc.save()
        set_limit(pd)  # In case of penury

    return True  # true == no error