#!/usr/bin/python3
import re
from datetime import datetime

from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User

from floreal.francais import articulate, plural, Plural
from caracole import settings

from html2text import html2text


class UserPhones(models.Model):
    """Associate one or several phone numbers to each user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)

    def __str__(self):
        return "%s %s: %s" % (self.user.first_name, self.user.last_name, self.phone)

    @property
    def display_number(self):
        if not hasattr(self, '_display_number'):
            n = "".join(k for k in self.phone if k.isdigit())
            if len(n) == 10:
                self._display_number = " ".join(n[i:i+2] for i in range(0, len(n), 2)) 
            else:
                self._display_number = self.phone
        return self._display_number

    @property
    def uri(self):
        if not hasattr(self, '_uri'):
            n = "".join(k for k in self.phone if k.isdigit())
            if len(n) == 10:
                self._uri = "tel:+33" + n[1:]
            else:
                self._uri = None
        return self._uri


class Network(models.Model):
    """One distribution network. Deliveries are passed for a whole network,
    then broken up into subgroups.
    The network has staff users, in charge of allowing, forbidding and pricing products
    in commands.

    Staff users are often also users allowed to order, but this isn't mandatory.
    Regular users are not stored diretly in the network: they're stored in the network's
    subgroup they belong to."""

    name = models.CharField(max_length=256, unique=True)
    staff = models.ManyToManyField(User, related_name='staff_of_network')
    regulators = models.ManyToManyField(User, related_name='regulator_of_network')
    producers = models.ManyToManyField(User, related_name='producer_of_network')
    members = models.ManyToManyField(User, related_name='member_of_network')
    candidates = models.ManyToManyField(User, related_name='candidate_of_network')
    auto_validate = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True, default=None)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    @property
    def description_text(self):
        return html2text(self.description)


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
    TERMINATED     = 'E'
    STATE_CHOICES = {
        PREPARATION:    "En préparation",
        ORDERING_ALL:   "Ouverte",
        ORDERING_ADMIN: "Admins",
        FROZEN:         "Gelée",
        TERMINATED:     "Terminée" }
    name = models.CharField(max_length=256)
    networks = models.ManyToManyField(Network)
    state = models.CharField(max_length=1, choices=STATE_CHOICES.items(), default=PREPARATION)
    description = models.TextField(null=True, blank=True, default=None)
    producer = models.ForeignKey(User, null=True, default=None, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def state_name(self):
        return self.STATE_CHOICES.get(self.state, 'Invalid state '+self.state)

    def subgroupMinState(self):
        states = self.subgroupstatefordelivery_set
        if states.count() < self.network.subgroup_set.count():
            return SubgroupStateForDelivery.DEFAULT  # Some unset subgroups
        else:
            return min(s.state for s in states.all())

    @property
    def description_text(self):
        return html2text(self.description)

    class Meta:
        verbose_name_plural = "Deliveries"
        ordering = ('-id',)


class Product(models.Model):
    """A product is only valid for one delivery. If the same product is valid across
    several deliveries, there are several homonym products in DB, one per delivery,
    so that changes in properties (prices, quotas etc.) don't affect other deliveries.
    """

    name = models.CharField(max_length=256)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE)
    price = models.DecimalField(decimal_places=2, max_digits=6)
    quantity_per_package = models.IntegerField(null=True, blank=True)
    unit = models.CharField(max_length=256, null=True, blank=True)
    quantity_limit = models.IntegerField(null=True, blank=True)
    unit_weight = models.DecimalField(decimal_places=3, max_digits=6, default=0.0, blank=True)
    quantum = models.DecimalField(decimal_places=2, max_digits=3, default=1, blank=True)
    description = models.TextField(null=True, blank=True, default=None)
    place = models.PositiveSmallIntegerField(null=True, blank=True, default=True)
    image = models.ImageField(null=True, default=None, blank=True)

    class Meta:
        # Problematic: during delivery modifications, some product names may transiently have a name
        # duplicated wrt another product to be renamed in the same update.
        # Moreover, in a future evolution, we'll want to allow several products with the same name but
        # different quantities, and a dedicated UI rendering for them.
        # unique_together = (('delivery', 'name'),)
        ordering = ('place', '-quantity_per_package', 'name',)

    def __str__(self):
        return self.name

    # Auto-fix frequent mis-usages    
    UNIT_AUTO_TRANSLATE = {
        "1": "pièce", "piece": "pièce", "1kg": "kg", "kilo": "kg", "unité": "pièce", "unite": "pièce"
    }

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.unit is None:
            self.unit = "pièce"
        else:
            self.unit = self.UNIT_AUTO_TRANSLATE.get(self.unit.lower(), self.unit)
        if self.unit == 'kg':
            self.unit_weight = 1.
        super(Product, self).save(force_insert, force_update, using, update_fields)

    @property
    def left(self):
        """How much of this product is there left?"""
        if self.quantity_limit is None:
            return None
        else:
            quantity_ordered = self.purchase_set.aggregate(t=Sum('quantity'))['t'] or 0
            return self.quantity_limit - quantity_ordered

    @property
    def description_text(self):
        return html2text(self.description)


class Purchase(models.Model):
    """A purchase is an intent to acquire quantity of a product  a delivery.
    If the product isn't available in unlimited quantity, then the ordered quantity
    might differ from the granted one."""

    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(decimal_places=3, max_digits=6)

    class Meta:
        unique_together = (('product', 'user'), )

    @property
    def price(self):
        return self.quantity * self.product.price

    @property
    def weight(self):
        return self.quantity * self.product.unit_weight

    @property
    def packages(self):
        qpp = self.product.quantity_per_package
        return self.quantity // qpp if qpp else None

    @property
    def out_of_package(self):
        packages = self.packages
        return self.quantity - packages if packages else self.quantity

    @property
    def max_quantity(self):
        """What's the current max quantity allowed for this order,
        assuming its current quantity is saved in DB so that product.left is accurate."""
        left = self.product.left
        return None if left is None else self.quantity + left

    def __str__(self, specify_user=False):
        fmt = "%(quantity)g%(mult)s%(unit)s %(prod_name)s à %(price).2f€"
        unit = self.product.unit
        result = fmt % {
            'mult': '×'if len(unit)>0 and unit[0].isdigit() else ' ',
            'quantity': self.quantity,
            'unit': plural(self.product.unit, self.quantity),
            'prod_name': articulate(self.product.name, self.quantity),
            'price': self.quantity * self.product.price,
            'user_name': self.user.__str__()
        }
        if specify_user:
            result += " pour %s %s" % (self.user.first_name, self.user.last_name)
        return result


class JournalEntry(models.Model):
    """Record of a noteworthy action by an admin, for social debugging purposes: changing delivery statuses,
    moving users around."""
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    date = models.DateTimeField(default=datetime.now)
    action = models.CharField(max_length=1024)

    @classmethod
    def log(cls, u, fmt, *args, **kwargs):
        try:
            action = fmt % (args or kwargs)
            date = datetime.now()
            if settings.USE_TZ:
                # Use a timezone if appropriate
                date = date.astimezone()
            cls.objects.create(user=u, date=date, action=action)
        except Exception:
            cls.objects.create("Failed to log, based on format " + repr(fmt))

    def __str__(self):
        n = self.user.email if self.user else "?"
        return (", ".join((n, self.date.isoformat(), self.action)))

class AdminMessage(models.Model):
    everyone = models.BooleanField(default=False)
    network = models.ForeignKey(Network, null=True, blank=True, default=None, on_delete=models.CASCADE)
    message = models.TextField()

    def __str__(self):
        d = []
        if self.everyone:
            d += ["Tout le monde"]
        if self.network is not None:
            d += ["Réseau "+self.network.name]
        if self.subgroup is not None:
            d += ["Sous-groupe "+self.subgroup.name]
        return ", ".join(d) + ": " + self.message
    
