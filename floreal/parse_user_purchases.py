from . import models as m

def parse_user_purchases(request):
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

    return True  # true == no error