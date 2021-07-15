#!/usr/bin/python3
import re
from datetime import datetime

from caracole import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from html2text import html2text
from django.utils import timezone
from django.utils.text import slugify
from typing import List
from floreal.francais import Plural, articulate, plural


class IdentifiedBySlug(models.Model):
    """
    Common ancestor of classes for which we want a slug,
    i.e. a URL-friendly unique identifier that's easier to remember than numeric primary keys.
    """

    slug = models.SlugField(unique=True, null=True)  # TODO eventually null will be false

    class Meta:
        abstract = True

    def slug_prefix(self):
        return slugify(self.name)[:24].strip("-")

    def save(self, **kwargs):
        if self.slug is None:
            # Find every object whose slug starts with the computed prefix, and add a number suffix if needed.
            # Make sure to perform only one DB request.
            #
            # Notice that this is only used on the first save of reasonably rarely created objects 
            # (e.g. products and purchases aren't identified by slugs), so it's probably not worth
            # optimizing with text_pattern_ops DB indexes or the likes.
            slug_prefix = slug = self.slug_prefix()
            similar_slugs = self.__class__.objects.filter(slug__startswith=slug_prefix).only("slug")
            used_suffixes = {slug[len(slug_prefix):] for obj in similar_slugs if (slug:=obj.slug) is not None}
            if "" not in used_suffixes:
                self.slug = slug_prefix
            else:
                suffix = -1
                while str(suffix) in used_suffixes:
                    suffix -= 1
                self.slug = slug_prefix + str(suffix)
        super().save(**kwargs)


def _user_network_getter(**kwargs):
    """
    Users of a network are listed by a ManyToMany+through relationship,
    which makes it cumbersome to retrive them with default Django accessors.
    This helper allows to add ``<quality>_of_network()`` accessors to auth
    user objects.
    """
    @property
    def user_of_network(self):
        now = timezone.now()
        return Network.objects.filter(
            networkmembership__in=NetworkMembership.objects
                .filter(user=self, **kwargs)
                .exclude(valid_from__gt=now)
                .exclude(valid_until__lt=now)
        )

    return user_of_network

User.staff_of_network = _user_network_getter(is_staff=True)
User.buyer_of_network = _user_network_getter(is_buyer=True)
User.producer_of_network = _user_network_getter(is_producer=True)
User.candidate_of_network = _user_network_getter(is_candidate=True)
User.regulator_of_network = _user_network_getter(is_regulator=True)


class FlorealUser(IdentifiedBySlug):
    """
    Associate a phone number to each user.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, null=True, blank=True, default=None)
    description = models.TextField(null=True, blank=True, default=None)
    image_description = models.ImageField(null=True, blank=True, default=None)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}: {self.display_number}"

    def slug_prefix(self):
        return slugify(f"{self.user.first_name} {self.user.last_name}")

    @property
    def display_number(self):
        if self.phone is None:
            return None
        if not hasattr(self, "_display_number"):
            n = "".join(k for k in self.phone if k.isdigit())
            if len(n) == 10:
                self._display_number = " ".join(
                    n[i : i + 2] for i in range(0, len(n), 2)
                )
            else:
                self._display_number = self.phone
        return self._display_number

    @property
    def uri(self):
        if not hasattr(self, "_uri"):
            n = "".join(k for k in self.phone if k.isdigit())
            if len(n) == 10:
                self._uri = "tel:+33" + n[1:]
            else:
                self._uri = None
        return self._uri


class NetworkSubgroup(IdentifiedBySlug):
    network = models.ForeignKey("Network", on_delete=models.CASCADE)
    name = models.CharField(max_length=32)

    def _filtered_members(self, **kwargs):
        ids = (
            nm["user_id"]
            for nm in self.networkmembership_set.filter(**kwargs).values("user_id")
        )
        return User.objects.filter(id__in=ids)

    @property
    def buyers(self):
        return self._filtered_members(is_buyer=True)

    @property
    def staff(self):
        return self._filtered_members(is_subgroup_staff=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['network', 'name'], name='unique_subgroup_name'),
        ]

class NetworkMembership(models.Model):
    """
    Relationship between a user and a network. Users can belong to a network
    under different qualities (buyer, staff, candidate etc) not mutually exclusive.
    Optionally they can belong through a subgroup. Partitionning a group into
    subgroups is an effective way to handle large, self-organized distributions.
    More on that (in French) in an upcoming guide.
    """
    network = models.ForeignKey("Network", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subgroup = models.ForeignKey(
        NetworkSubgroup, null=True, default=None, on_delete=models.CASCADE
    )
    is_staff = models.BooleanField(default=False)
    is_subgroup_staff = models.BooleanField(default=False)
    is_producer = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=True)
    is_regulator = models.BooleanField(default=False)
    is_candidate = models.BooleanField(default=False)

    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(default=None, null=True, blank=True)

    def __str__(self):
        r = self.user.username + " ∈ " + self.network.name
        if self.subgroup is not None:
            r += "/" + self.subgroup.name
        roles = [
            q
            for q in (
                "staff",
                "subgroup_staff",
                "producer",
                "buyer",
                "regulator",
                "candidate",
            )
            if getattr(self, "is_" + q)
        ]
        r += " as " + "+".join(roles)
        return r

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['network', 'user'], name='unique_membership'),
            # TODO: check that you can't be both buyer and candidate
        ]

class Network(IdentifiedBySlug):
    """
    One distribution network. Deliveries are passed for a whole network,
    then broken up into subgroups.
    The network has staff users, in charge of allowing, forbidding and pricing products
    in commands.
    """

    name = models.CharField(max_length=256, unique=True)
    members = models.ManyToManyField(
        User, related_name="member_of_network", through=NetworkMembership
    )
    auto_validate = models.BooleanField(default=False)
    visible =models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True, default=None)
    short_description = models.TextField(null=True, blank=True, default=None)
    image_description = models.ImageField(null=True, blank=True, default=None)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def _filtered_members(self, **kwargs):
        return User.objects.filter(
            networkmembership__in=NetworkMembership.objects.filter(
                network=self, **kwargs
            )
        )

    @property
    def staff(self):
        return self._filtered_members(is_staff=True)

    @property
    def buyers(self):
        return self._filtered_members(is_buyer=True)

    @property
    def producers(self):
        return self._filtered_members(is_producer=True)

    @property
    def candidates(self):
        return self._filtered_members(is_candidate=True)

    @property
    def regulators(self):
        return self._filtered_members(is_regulator=True)

    @property
    def description_text(self):
        return html2text(self.description)

    @property
    def grouped(self):
        return self.networksubgroup_set.exists()

    def active_deliveries(self):
        return self.delivery_set.filter(state__in="ABCD")


class Delivery(IdentifiedBySlug):
    """A command of products, for a given network. It's referenced by product
    descriptions and by purchase orders.

    It can be open (regular users are allowed to make and modify purchases),
    closed (only subgroup staff members can modify purchases), or
    delivered (nobody can modify it)."""

    (PREPARATION, ORDERING_ALL, ORDERING_ADMIN, FROZEN, TERMINATED) = "ABCDE"
    STATE_CHOICES = {
        PREPARATION: "En préparation",
        ORDERING_ALL: "Ouverte",
        ORDERING_ADMIN: "Admins",
        FROZEN: "Gelée",
        TERMINATED: "Terminée",
    }
    name = models.CharField(max_length=256)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    state = models.CharField(
        max_length=1, choices=STATE_CHOICES.items(), default=PREPARATION
    )
    description = models.TextField(null=True, blank=True, default=None)
    producer = models.ForeignKey(
        User, null=True, default=None, on_delete=models.SET_NULL
    )
    freeze_date = models.DateField(null=True, blank=True, default=None)
    distribution_date = models.DateField(null=True, blank=True, default=None)
    visible = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def state_name(self):
        return self.STATE_CHOICES.get(self.state, "Etat Invalide " + self.state)

    @property
    def description_text(self):
        return html2text(self.description) if self.description is not None else ""

    class Meta:
        verbose_name_plural = "Deliveries"
        ordering = ("-id",)


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
    unit_weight = models.DecimalField(
        decimal_places=3, max_digits=6, default=0.0, blank=True
    )
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
        ordering = (
            "place",
            "-quantity_per_package",
            "name",
        )
        constraints = [
            models.UniqueConstraint(fields=['delivery', 'name'], name='unique_product'),
        ]

    def __str__(self):
        return self.name

    # Auto-fix frequent mis-usages
    UNIT_AUTO_TRANSLATE = {
        "1": "pièce",
        "piece": "pièce",
        "1kg": "kg",
        "kilo": "kg",
        "unité": "pièce",
        "unite": "pièce",
    }

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.unit is None:
            self.unit = "pièce"
        else:
            self.unit = self.UNIT_AUTO_TRANSLATE.get(self.unit.lower(), self.unit)
        if self.unit == "kg":
            self.unit_weight = 1.0
        super(Product, self).save(force_insert, force_update, using, update_fields)

    @property
    def left(self):
        """How much of this product is there left?"""
        if self.quantity_limit is None:
            return None
        else:
            quantity_ordered = self.purchase_set.aggregate(t=Sum("quantity"))["t"] or 0
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
            "mult": "×" if len(unit) > 0 and unit[0].isdigit() else " ",
            "quantity": self.quantity,
            "unit": plural(self.product.unit, self.quantity),
            "prod_name": articulate(self.product.name, self.quantity),
            "price": self.quantity * self.product.price,
            "user_name": self.user.__str__(),
        }
        if specify_user:
            result += " pour %s %s" % (self.user.first_name, self.user.last_name)
        return result

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name='unique_purchase'),
        ]
        

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
        return ", ".join((n, self.date.isoformat(), self.action))


class AdminMessage(models.Model):
    network = models.ForeignKey(
        Network, null=True, default=None, on_delete=models.CASCADE
    )
    message = models.TextField()

    def __str__(self):
        who = "Tout le monde" if self.network is None else "Réseau " + self.network.name
        return who + " : " + self.message
