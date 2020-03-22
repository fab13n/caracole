#!/usr/bin/python
# -*- coding: utf-8 -*-

from floreal import models as m

def allocate(limit, wishes):
    """ Resources allocation in case of penury: When a list of consumers want
    some resources, and that resource exists in insufficient quantity to
    satisfy the total demand, a way must be found to allocate existing resources
    while minimizing unsatisfaction.

    This heuristic finds a ceiling, a maximal authorized quantity of
    resources allowed per consumer. Those who asked less than the
    ceiling will receive what they asked for, others will receive the
    ceiling quantity. resources are attributed by integral values, so
    there might be some resources left, although less than 1unit per
    unsatisfied consumer. The couple of remaining resource units beyond
    the ceiling are attributed to the consumers who asked for the most
    resources, i.e. presumably the most unsatisfied ones.

    :param limit: total quantity allocated.
    :param wishes: quantities wished by each customer (dictionary, arbitrary key types).
    :return:  quantities allocated to each customer (dictionary, same keys as above).
    """
    wish_values = wishes.values()
    if sum(wish_values) <= limit:
        # print "There's enough for everyone!"
        return wishes
    unallocated = limit  # resources left to attribute
    granted = {k: 0 for k in wishes.keys()}  # what consumers have been granted so far
    n_unsatisfied = len(wishes) - wish_values.count(0)  # nb of consumers still unsatisfied
    ceiling = 0  # current limit (increases until everything is allocated)

    # first stage: find a ceiling that leaves less than one unit per unsatisfied buyer
    while unallocated >= n_unsatisfied:
        lot = unallocated / n_unsatisfied  # We can safely distribute at least this much
        ceiling += lot
        # print ("%i units left; allocating %i units to %i unsatisfied people" % (unallocated, lot, n_unsatisfied))
        for k, wish_k in wishes.items():
            wish_more_k = wish_k - granted[k]
            if wish_more_k > 0:  # this consumer isn't satisfied yet, give him some more
                lot_k = min(wish_more_k, lot)  # don't give more than what he asked for, though.
                # print ("person %i wishes %i more unit, receives %i"%(i, wish_i, lot_i))
                granted[k] += lot_k
                unallocated -= lot_k
                if granted[k] == wishes[k]:
                    n_unsatisfied -= 1  # He's satisfied now!

    # 2nd stage: give the remaining units, one by one, to biggest unsatisfied buyers
    got_leftover = sorted(wishes.keys(), key=lambda k: granted[k]-wishes[k])[0:unallocated]
    # print ("%i more units to distribute, they will go to %s" % (unallocated, got_leftover))
    for k in got_leftover:
        granted[k] += 1
        unallocated -= 1

    # Some invariant checks
    if True:
        assert unallocated == 0
        assert sum(granted.values()) == limit
        for k in wishes.keys():
            assert granted[k] <= wishes[k]
            assert granted[k] <= ceiling+1

    return granted


def set_limit(pd, last_pc=None):
    """
    Use `allocate()` to ensure that product `pd` hasn't been granted in amount larger than `limit`.
    :param pd: product featuring the quantity limit
    """
    # TODO: in case of limitation, first cancel extra users' orders
    if pd.quantity_limit is None:  # No limit, granted==ordered for everyone
        return

    purchases = m.Purchase.objects.filter(product=pd)
    wishes = {pc.user_id: int(pc.quantity) for pc in purchases}
    formerly_granted = {pc.user_id: int(pc.quantity) for pc in purchases}

    if last_pc is not None:
        # First limit the last purchase
        wished = sum(wishes.values())
        excess = wished - pd.quantity_limit
        if excess <= 0:
            return  # No penury
        elif last_pc.quantity > excess:
            # Fixing the last purchase is enough to cancel the excess
            last_pc.quantity -= excess
            last_pc.save()
            return
        else:
            # The last purchase must be fixed, but that won't be enough
            del wishes[last_pc.user_id]
            last_pc.delete()
            # Then go on to penury re-allocation

    # Call the algorithm
    granted = allocate(int(pd.quantity_limit), wishes)

    # Save changed purchases into DB
    for pc in purchases:
        uid = pc.user_id
        if formerly_granted[uid] != granted[uid]:  # Save some DB accesses
            pc.quantity = granted[uid]
            print "%s %s had their purchase of %s modified: ordered %s, formerly granted %s, now granted %s" % (
                pc.user.first_name, pc.user.last_name, pc.product.name, pc.quantity, formerly_granted[uid], pc.quantity
            )
            pc.save(force_update=True)
