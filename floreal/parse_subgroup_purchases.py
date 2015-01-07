import re
from . import models as m


def parse_subgroup_purchases(request):
    """
    Parse responses from subgroup purchase editions.
    :param request:
    :return:
    """

    d = request.POST
    for pd, u in re.findall(r'pd(\d+)u(\d+)', d['modified']):
        ordered = float(d['pd%su%s' % (pd, u)])
        try:
            pc = m.Purchase.objects.get(product_id=pd, user_id=u)
            if ordered != 0:
                print "Updating purchase %d" % pc.id
                pc.ordered = ordered
                pc.granted = ordered
                pc.save(force_update=True)
            else:
                print "Cancelling purchase %d" % pc.id
                pc.delete()
        except m.Purchase.DoesNotExist:
            if ordered != 0:
                print "Creating purchase for pd=%s, u=%s, q=%f" % (pd, u, ordered)
                pc = m.Purchase.objects.create(product_id=pd, user_id=u, ordered=ordered, granted=ordered)

    return True  # true == no error
