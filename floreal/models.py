#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from datetime import datetime

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

from caracole import settings

# A user belongs can belong to several networks, through one subgroup per network.
# They might also be staff of several subgroups,
# and staff of several networks.
# Symmetrically, subgroups and networks can each have several staff.


class Plural(models.Model):
    """Remember the plural of product and unit names.
    Django supports plurals for words occurring verbatim in templates,
    but not for words coming from the DB."""
    singular = models.CharField(max_length=64, unique=True)
    plural = models.CharField(max_length=64, null=True, blank=True, default=None)

    def __unicode__(self):
        return "%s/%s" % (self.singular, self.plural)


# Cache for plurals, to avoid many DB lookups when a pluralized word appears many times in a page.
_plural_cache = {}

# TODO: implement a cache?
def plural(noun, n=None):
    """Tries to retrieve of guess the plural of a singular French word.
    It would be great to hook this up to a (possibly online) dictionary.

    :param noun: the French noun to try and pluralize
    :param n: number of stuff (optional): don't pluralize if |n| < 2.
    :return: pluralized noun."""

    if n is not None and -2 < n < 2:
        return noun  # No need to pluralize

    try:
        return _plural_cache[noun]  # Found in cache
    except KeyError:
        pass

    try:
        r = Plural.objects.get(singular=noun).plural
        if r is not None:
            _plural_cache[noun] = r
            return r
    except Plural.DoesNotExist:
        # Put the singular alone in DB, so that we know it needs to be filled
        Plural.objects.create(singular=noun, plural=None)

    # Not found in DB, or found to be None: try to guess it
    if noun[-1] == 's' or noun[-1] == 'x':
        r = noun  # Probably invariant
    elif noun[-2:] == 'al':
        r = noun[:-2] + 'aux'
    elif noun[-3:] == 'eau':
        r = noun + 'x'
    else:
        r = noun + 's'  # probably a regular plural

    _plural_cache[noun] = r
    return r


def articulate(noun, n=1):
    """Prepend an appropriate French article to a word.
    Caveat: doesn't handle 'y' nor 'h' correctly.

    :param noun: the noun in need of an article
    :param n: quantity of the noun, to determine whether it needs to be pluralized
    :return: the noun with an indefinite article, possibly in the plural form."""

    if 'aeiou'.count(noun[0].lower()):
        return "d'" + plural(noun, n)
    else:
        return "de " + plural(noun, n)


class Network(models.Model):
    """One distribution network. Deliveries are passed for a whole network,
    then broken up into subgroups.
    The network has staff users, in charge of allowing, forbidding and pricing products
    in commands.

    Staff users are often also users allowed to order, but this isn't mandatory.
    Regular users are not stored diretly in the network: they're stored in the network's
    subgroup they belong to."""

    name = models.CharField(max_length=64, unique=True)
    staff = models.ManyToManyField(User, related_name='staff_of_network')

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name


class Subgroup(models.Model):
    """Subgroup of a network. Each subgroup has a set of regular users, and a set of staff
    users. Staff users are allowed to modify the commands of their group users' purchases,
    even if the delivery is closed (but not if it's already delivered). Staff users are
    typically also regular users, but this is not mandatory.

    Each subgroup has an 'Extra' user; staff users can order on behalf of the extra user,
    so that the subgroup's order sums up to entire boxes, if network staff wishes so.
    Extra users are allowed to order a negative quantity of products."""

    name = models.CharField(max_length=64)
    network = models.ForeignKey(Network)
    extra_user = models.ForeignKey(User, null=True, blank=True, related_name='+')
    # Users might only be staff of one subgroup per network
    staff = models.ManyToManyField(User, related_name='staff_of_subgroup')
    users = models.ManyToManyField(User, related_name='user_of_subgroup')
    candidates = models.ManyToManyField(User, related_name='candidate_of_subgroup', through='Candidacy')

    class Meta:
        unique_together = (('network', 'name'),)
        ordering = ('name',)

    def __unicode__(self):
        return "%s/%s" % (self.network.name, self.name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """If the extra user is missing, create it before saving."""
        if not self.extra_user:
            extra_username = "extra-%s" % self.name.lower()
            if User.objects.filter(username=extra_username).exists():
                extra_username = "extra-%s-%s" % (self.network.name.lower(), self.name.lower())
            # TODO: doesn't necessarily end in gmail.com!
            extra_email = settings.EMAIL_HOST_USER.replace("@gmail.com", "+" + extra_username + "@gmail.com")
            self.extra_user = User.objects.create(username=extra_username,
                                                  email=extra_email,
                                                  first_name="extra",
                                                  last_name=self.name.capitalize(),
                                                  last_login=datetime.now())
            self.users.add(self.extra_user)
        super(Subgroup, self).save(force_insert=force_insert, force_update=force_update,
                                   using=using, update_fields=update_fields)

    @property
    def sorted_users(self):
        if not self.extra_user:
            raise ValueError("Subgroup "+self.network.name+"/"+self.name+" has no extra user")
        normal_users = [u for u in self.users.all() if u != self.extra_user]
        normal_users.sort(key=lambda u: (u.last_name.lower(), u.first_name.lower()))
        return [self.extra_user] + normal_users


class Candidacy(models.Model):
    user = models.ForeignKey(User)
    subgroup = models.ForeignKey(Subgroup)
    message = models.TextField(null=True, blank=True)  # Currently unused, might be used to communicate with admins


class Delivery(models.Model):
    """A command of products, for a given network. It's referenced by product
    descriptions and by purchase orders.

    It can be open (regular users are allowed to make and modify purchases),
    closed (only subgroup staff members can modify purchases), or
    delivered (nobody can modify it)."""

    PREPARATION    = 'A'
    ORDERING_ALL   = 'B'
    ORDERING_ADMIN = 'C'
    FROZEN         = 'D'
    REGULATING     = 'E'
    TERMINATED     = 'F'
    STATE_CHOICES = {
        PREPARATION:    u"En préparation",
        ORDERING_ALL:   u"Ouverte",
        ORDERING_ADMIN: u"Admins",
        FROZEN:         u"Gelée",
        REGULATING:     u"Régularisation",
        TERMINATED:     u"Terminée" }
    name = models.CharField(max_length=64)
    network = models.ForeignKey(Network)
    state = models.CharField(max_length=1, choices=STATE_CHOICES.items(), default=PREPARATION)

    def get_stateForSubgroup(self, sg):
        try:
            return self.subgroupstatefordelivery_set.get(delivery=self, subgroup=sg).state
        except models.ObjectDoesNotExist:
            return SubgroupStateForDelivery.DEFAULT

    def set_stateForSubgroup(self, sg, state):
        try:
            x = self.subgroupstatefordelivery_set.get(delivery=self, subgroup=sg)
            x.state = state
            x.save()
        except models.ObjectDoesNotExist:
            SubgroupStateForDelivery.objects.create(delivery=self, subgroup=sg, state=state)

    def __unicode__(self):
        return "%s/%s" % (self.network.name, self.name)

    def state_name(self):
        return self.STATE_CHOICES.get(self.state, 'Invalid state '+self.state)

    def subgroupMinState(self):
        states = self.subgroupstatefordelivery_set
        if states.count() < self.network.subgroup_set.count():
            return SubgroupStateForDelivery.DEFAULT  # Some unset subgroups
        else:
            return min(s.state for s in states.all())

    class Meta:
        verbose_name_plural = "Deliveries"
        unique_together = (('network', 'name'),)
        ordering = ('-id',)


class SubgroupStateForDelivery(models.Model):
    INITIAL              = 'X'
    READY_FOR_DELIVERY   = 'Y'
    READY_FOR_ACCOUNTING = 'Z'
    DEFAULT = INITIAL
    STATE_CHOICES = {
        INITIAL:              u"Non validé",
        READY_FOR_DELIVERY:   u"Commande validée",
        READY_FOR_ACCOUNTING: u"Compta validée"}
    state = models.CharField(max_length=1, choices=STATE_CHOICES.items(), default=DEFAULT)
    delivery = models.ForeignKey(Delivery)
    subgroup = models.ForeignKey(Subgroup)


#class Section(models.Model):
#    """Products are optionally sorted into sections, so that their display to customers can be organized.
#    The list of available sections is specific to a network. Sections can be nested."""
#    name = models.CharField(max_length=64)
#    network = models.ForeignKey(Network)
#    parent = models.ForeignKey('Section', null=True, blank=True, default=None)
#    is_active = models.BooleanField(default=True)  # Use this instead of deleting unused sections


class Product(models.Model):
    """A product is only valid for one delivery. If the same product is valid across
    several deliveries, there are several homonym products in DB, one per delivery,
    so that changes in properties (prices, quotas etc.) don't affect other deliveries.
    """

    name = models.CharField(max_length=64)
    # section = models.ForeignKey(Section, null=True, blank=True, default=None)
    delivery = models.ForeignKey(Delivery)
    price = models.DecimalField(decimal_places=2, max_digits=6)
    quantity_per_package = models.IntegerField(null=True, blank=True)
    unit = models.CharField(max_length=64, null=True, blank=True)
    quantity_limit = models.IntegerField(null=True, blank=True)
    unit_weight = models.DecimalField(decimal_places=3, max_digits=6, default=0.0, blank=True)
    quantum = models.DecimalField(decimal_places=2, max_digits=3, default=1, blank=True)

    class Meta:
        unique_together = (('delivery', 'name'),)
        ordering = ('-quantity_per_package', 'name',)

    def __unicode__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.unit == 'kg':
            self.unit_weight = 1.
        super(Product, self).save(force_insert, force_update, using, update_fields)


class Purchase(models.Model):
    """A purchase is an intent to acquire quantity of a product  a delivery.
    If the product isn't available in unlimited quantity, then the ordered quantity
    might differ from the granted one."""

    user = models.ForeignKey(User, null=True)
    product = models.ForeignKey(Product)
    ordered = models.DecimalField(decimal_places=3, max_digits=6)
    granted = models.DecimalField(decimal_places=3, max_digits=6)

    class Meta:
        unique_together = (('product', 'user'), )

    @property
    def is_satisfied(self):
        return self.granted == self.ordered

    @property
    def price(self):
        return self.granted * self.product.price

    @property
    def weight(self):
        return self.granted * self.product.unit_weight

    def __unicode__(self, specify_user=False):
        if self.ordered == self.granted:
            fmt = u"%(granted)g%(mult)s%(unit)s %(prod_name)s à %(price).2f€"
        else:
            fmt = u"%(granted)g%(mult)s%(unit)s (au lieu de %(ordered)g) %(prod_name)s à %(price).2f€"
        result = fmt % {
            'mult': u'×' if self.product.unit[0].isdigit() else u' ',
            'granted': self.granted,
            'ordered': self.ordered,
            'unit': plural(self.product.unit, self.granted),
            'prod_name': articulate(self.product.name, self.granted),
            'price': self.granted * self.product.price,
            'user_name': self.user.__unicode__()
        }
        if specify_user:
            result += " pour %s %s" % (self.user.first_name, self.user.last_name)
        return result


class LegacyPassword(models.Model):
    """Used to authentify legacy users, regeistered with the old web2py version of the app,
    the first time they log in. At first login, their password is migrated to Django's regular
    authentication backend, so it normally happens only once par legacy user."""
    email = models.CharField(max_length=64)
    password = models.CharField(max_length=200)
    circle = models.CharField(max_length=32)
    migrated = models.BooleanField(default=False)


class Order(object):
    """Sum-up of what a given user has ordered in a given delivery."""

    def __init__(self, user, delivery, purchases=None):
        """Create the order sum-up.
        :param user: who ordered
        :param delivery: when
        :param purchases: if the list of purchases is passed, it isn't extracted from delivery and user.
            Intended for internal use.
        :return: an instance with fields `user`, `delivery`, `price` and `purchases`
        (an iterable of relevant `Purchase` instances)."""

        self.user = user
        self.delivery = delivery
        if purchases:
            self.purchases = purchases
            self.price = None
        else:
            self.purchases = Purchase.objects.filter(product__delivery=delivery, user=user)
            self.price = sum(p.price for p in self.purchases)
            self.weight = sum(p.weight for p in self.purchases)

    @classmethod
    def by_user_and_product(cls, delivery, users, products=None):
        """Compute a dict of orders, for several users, more efficiently than by performing `len(users)` DB queries.
        Purchases are in a list, sorted according to the list `product` if passed, by product name otherwise.
        If a product hasn't been purchased by a user, `None` is used as a placeholder in the purchases list.

        :param delivery: for which delivery
        :param users: iterable over users
        :param products: ordered list of products; normally, the products available in `delivery`.
        :return: a user -> orders_list_indexed_as_products dictionary for all `users`."""

        class DummyPurchase(object):
            """"Dummy purchase, to be used as a stand-in in purchas tables when a product
            hasn't been purchased by a user."""
            def __init__(self, product, user):
                self.product = product
                self.user = user
                self.price = 0
                self.ordered = 0
                self.granted = 0

            def __nonzero__(self):
                return False

        if not products:
            products = delivery.product_set.all()
        purchases_by_user = {u: {} for u in users}
        prices = {u: 0 for u in users}
        for pc in Purchase.objects.filter(product__delivery=delivery, user__in=users):
            purchases_by_user[pc.user][pc.product] = pc
            prices[pc.user] += pc.price

        def purchase_line(u):
            return [purchases_by_user[u].get(pd, None) or DummyPurchase(pd, u) for pd in products]

        orders = {u: Order(u, delivery, purchases=purchase_line(u)) for u in users}
        for u in users:
            orders[u].price = prices[u]
        return orders

