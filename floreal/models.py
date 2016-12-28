#!/usr/bin/python
# -*- coding: utf-8 -*-

from datetime import datetime

from django.db import models
from django.contrib.auth.models import User

from floreal.francais import articulate, plural, Plural
from caracole import settings


class UserPhones(models.Model):
    """Associate one or several phone numbers to each user."""
    user = models.ForeignKey(User)
    phone = models.CharField(max_length=20)

    def __unicode__(self):
        return "%s %s: %s" % (self.user.first_name, self.user.last_name, self.phone)


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
    auto_validate = models.BooleanField(default=False)

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
    auto_validate = models.BooleanField(default=False)

    class Meta:
        unique_together = (('network', 'name'),)
        ordering = ('name',)

    def __unicode__(self):
        return "%s/%s" % (self.network.name, self.name)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """If the extra user is missing, create it before saving."""
        if not self.extra_user:
            missing_extra = True
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
        else:
            missing_extra = False
        super(Subgroup, self).save(force_insert=force_insert, force_update=force_update,
                                   using=using, update_fields=update_fields)
        if missing_extra:
            self.users.add(self.extra_user)

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


class Product(models.Model):
    """A product is only valid for one delivery. If the same product is valid across
    several deliveries, there are several homonym products in DB, one per delivery,
    so that changes in properties (prices, quotas etc.) don't affect other deliveries.
    """

    name = models.CharField(max_length=64)
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
    quantity = models.DecimalField(decimal_places=3, max_digits=6)

    class Meta:
        unique_together = (('product', 'user'), )

    @property
    def price(self):
        return self.quantity * self.product.price

    @property
    def weight(self):
        return self.quantity * self.product.unit_weight

    def __unicode__(self, specify_user=False):
        fmt = u"%(quantity)g%(mult)s%(unit)s %(prod_name)s à %(price).2f€"
        unit = self.product.unit
        result = fmt % {
            'mult': u'×'if len(unit)>0 and unit[0].isdigit() else u' ',
            'quantity': self.quantity,
            'unit': plural(self.product.unit, self.quantity),
            'prod_name': articulate(self.product.name, self.quantity),
            'price': self.quantity * self.product.price,
            'user_name': self.user.__unicode__()
        }
        if specify_user:
            result += " pour %s %s" % (self.user.first_name, self.user.last_name)
        return result


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
                self.quantity = 0

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


class JournalEntry(models.Model):
    """Record of a noteworthy action by an admin, for social debugging purposes: changing delivery statuses,
    moving users around."""
    user = models.ForeignKey(User, null=True)
    date = models.DateTimeField(default=datetime.now)
    action = models.CharField(max_length=256)

    @classmethod
    def log(cls, u, fmt, *args, **kwargs):
        cls.objects.create(user=u, date=datetime.now(), action=fmt % (args or kwargs))


class Discrepancy(models.Model):
    """Log of a discrepancy between what's been ordered and what's actually been paid for in a given subgroup.
    """
    product = models.ForeignKey(Product)
    amount = models.DecimalField(decimal_places=3, max_digits=9)
    subgroup = models.ForeignKey(Subgroup)
    reason = models.CharField(max_length=256)

