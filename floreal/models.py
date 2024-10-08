#!/usr/bin/python3
import re
from datetime import datetime, timedelta
from functools import cached_property
from collections import defaultdict
from decimal import Decimal
from time import time

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, Sum, F
from django.db.models.functions import Now, TruncDate
from django.utils import timezone
from django.utils.text import slugify
from html2text import html2text
from unidecode import unidecode

from floreal.francais import Plural, articulate, plural
from villes.models import Ville

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

class Mapped(models.Model):

    longitude = models.FloatField(null=True, blank=True, default=None)
    latitude = models.FloatField(null=True, blank=True, default=None)

    # TODO add by-class or by-instance icons
    # TODO add commune

    class Meta:
        abstract = True


# def _user_network_getter(**kwargs):
#     """
#     Users of a network are listed by a ManyToMany+through relationship,
#     which makes it cumbersome to retrive them with default Django accessors.
#     This helper allows to add ``<quality>_of_network()`` accessors to auth
#     user objects.
#     """
#     @property
#     def user_of_network(self):
#         return Network.objects.filter(
#             networkmembership__in=NetworkMembership.objects
#                 .filter(user=self, **kwargs)
#                 .exclude(valid_from__gt=Now())
#                 .exclude(valid_until__lt=Now())
#         )

#     return user_of_network

# User.staff_of_network = _user_network_getter(is_staff=True)
# User.buyer_of_network = _user_network_getter(is_buyer=True)
# User.producer_of_network = _user_network_getter(is_producer=True)
# User.candidate_of_network = _user_network_getter(is_candidate=True)


class FlorealUser(IdentifiedBySlug, Mapped):
    """
    Associate a phone number to each user.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, null=True, blank=True, default=None)
    description = models.TextField(null=True, blank=True, default=None)
    image_description = models.ImageField(null=True, blank=True, default=None)
    pseudonym = models.CharField(max_length=User.username.field.max_length, null=True, blank=True, default=None)

    def __str__(self):
        return self.pseudonym or f"{self.user.first_name} {self.user.last_name}"

    def slug_prefix(self):
        return slugify(f"{self.user.first_name} {self.user.last_name}")

    @property
    def display_name(self):
        if self.pseudonym:
            return self.pseudonym
        else:
            u = self.user
            return u.first_name + " " + u.last_name

    @cached_property
    def display_number(self):
        if self.phone is None:
            return None
        n = "".join(k for k in self.phone if k.isdigit())
        if len(n) == 10:
            return " ".join(
                n[i : i + 2] for i in range(0, len(n), 2)
            )
        else:
            return self.phone
    
    @cached_property
    def uri(self):
        if self.phone is None:
            return None
        n = "".join(k for k in self.phone if k.isdigit())
        if len(n) == 10:
            return "tel:+33" + n[1:]
        else:
            return None

    @cached_property
    def has_some_admin_rights(self):
        u = self.user
        return u.is_staff or NetworkMembership.objects.filter(
            Q(is_staff=True) | Q(is_producer=True) | Q(is_subgroup_staff=True),
            user_id=u.id, valid_until=None, ).exists()


class NetworkSubgroup(IdentifiedBySlug):
    network = models.ForeignKey("Network", on_delete=models.CASCADE)
    name = models.CharField(max_length=32)

    def __str__(self) -> str:
        return f"{self.network.name} / {self.name}"

    # def _filtered_members(self, date=None, **kwargs):
    #     date |= Now()
    #     ids = (
    #         nm["user_id"]
    #         for nm in (self.networkmembership_set
    #             .filter(**kwargs)
    #             .filter(valid_from__lte=date)
    #             .filter(Q(valid_to=None)|Q(valid_to__gte=date))
    #             .values("user_id")
    #         )
    #     )
    #     return User.objects.filter(id__in=ids)

    # @property
    # def buyers(self):
    #     return self._filtered_members(is_buyer=True)

    # @property
    # def staff(self):
    #     return self._filtered_members(is_subgroup_staff=True)

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
    is_candidate = models.BooleanField(default=False)

    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(default=None, null=True, blank=True)

    def __str__(self):
        r = "" if self.valid_until is None else "(FORMER) "
        r += self.user.username + " ∈ " + self.network.name
        if self.subgroup is not None:
            r += "/" + self.subgroup.name
        roles = [
            q
            for q in (
                "staff",
                "subgroup_staff",
                "producer",
                "buyer",
                "candidate",
            )
            if getattr(self, "is_" + q)
        ]
        r += " as " + "+".join(roles)
        return r

    class Meta:
        constraints = [
            # The point is, there's only one currently valid (valid_until=None) membership for a user/network
            models.UniqueConstraint(fields=['network', 'user', 'valid_until'], name='unique_membership'),
        ]

class Network(IdentifiedBySlug, Mapped):
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
    active = models.BooleanField(default=True)
    visible = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True, default=None)
    short_description = models.TextField(null=True, blank=True, default=None)
    image_description = models.ImageField(null=True, blank=True, default=None)
    ville = models.ForeignKey(Ville, null=True, blank=True, default=None, on_delete=models.SET_NULL)
    search_string = models.TextField(max_length=256, default="")

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def description_text(self):
        return html2text(self.description)

    @property
    def grouped(self):
        return self.networksubgroup_set.exists()

    def save(self, **kwargs):
        s = [
            self.name,
            self.short_description or "",   
        ]
        if self.ville:
            s += [
                self.ville.nom_simple,
                str(self.ville.departement)
            ]
        self.search_string = re.sub(r"[^a-z0-9]+", " ", unidecode(" ".join(s).lower()))
        if self.ville and self.latitude is None:
            self.latitude = self.ville.latitude_deg
            self.longitude = self.ville.longitude_deg
        return super().save(**kwargs)


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
    creation_date = models.DateTimeField(auto_now_add=True)
    freeze_date = models.DateField(null=True, blank=True, default=None)
    distribution_date = models.DateField(null=True, blank=True, default=None)

    def __str__(self):
        return self.name

    def state_name(self):
        return self.STATE_CHOICES.get(self.state, "Etat Invalide " + self.state)

    @property
    def description_text(self):
        return html2text(self.description) if self.description is not None else ""

    @classmethod
    def freeze_overdue_deliveries(cls):
        """
        Put in "FREEZE" state the deliveries which are still open,
        and whose freeze date was yesterday.
        """
        overdue = cls.objects.filter(
            state=cls.ORDERING_ALL,
            freeze_date=timezone.localdate() - timedelta(days=1)
        )

        if len(overdue) > 0:
            overdue.update(
                state=cls.FROZEN
            )
            overdue_ids = ", ".join([f"dv-{dv.id}" for dv in overdue])
            JournalEntry.log(None, "Auto-froze overdue deliveries %s", overdue_ids)
        else:
            JournalEntry.log(None, "No overdue deliveries to freeze")

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
    quantum = models.DecimalField(decimal_places=2, max_digits=5, default=1, blank=True)
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
            # There can be several products named the same, e.g. in different quantities.
            # models.UniqueConstraint(fields=['delivery', 'name'], name='unique_product'),
        ]

    def __str__(self):
        return self.name

    # Auto-fix frequent mis-usages
    UNIT_AUTO_TRANSLATE = {
        "1": "pièce",
        "piece": "pièce",
        "kilo": "kg",
        "gr": "g",
        "unité": "pièce",
        "unite": "pièce",
    }

    UNIT_TRANSLATE_REGEXP = re.compile(r"""
        ^
        ([0-9]+) 
        (?:  [,.]  ([0-9]+)  )?
        \s*
        ([A-Za-z]+)
        $""", re.VERBOSE)

    @classmethod
    def _normalize_unit(cls, u):
        w = None
        if u is None:
            u = "pièce"
        elif (rm:=cls.UNIT_TRANSLATE_REGEXP.match(u)):
            integral, frac, unit_name = rm.groups()
            # the separator may be a french "," rather than ".";
            # and we don't want to introduce extra ".0" suffix in integral values
            value = float(integral + "." + frac) if frac else int(integral) 
            unit_name = cls.UNIT_AUTO_TRANSLATE.get(unit_name.lower(), unit_name)
            if value == 1:
                u = unit_name
            elif (integral, unit_name) == ("0", "kg"):
                w = value
                u = f"{int(1000 * value)}g"
            elif (integral, unit_name) == ("0", "l"):
                ml = int(1000 * value)
                if ml % 10 == 0:
                    u = f"{ml // 10}cl"
                else:
                    u = f"{ml}ml"
            else:
                u = str(value) + unit_name
        else:
            u = cls.UNIT_AUTO_TRANSLATE.get(u.lower(), u)
        return u, w

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        self.unit, w = self._normalize_unit(self.unit)
        if w is not None:
            self.unit_weight = w
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
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


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
        
class Bestof(models.Model):
    """
    Attempt to gamify the system: score users according to their absolute and relative cumulated purchases.
    """
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    total = models.DecimalField(decimal_places=2, max_digits=10)
    rank = models.IntegerField()
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user'], name="unique_user"),
        ]
        ordering = ["rank"]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}: #{self.rank}, {self.total}€"

    @classmethod
    def update(cls):
        time0 = time()
        r = defaultdict(Decimal)
        for pc in (
            Purchase.objects.all()
            .select_related("user", "product")
            .annotate(pp=F("product__price") * F("quantity"))
        ):
            r[pc.user_id] += pc.pp
        batch = [
            cls(user_id=uid, total=total, rank=rank_from_0+1) 
            for rank_from_0, (uid, total) in enumerate(
                sorted(r.items(), key=lambda item: item[1], reverse=True)
        )]

        cls.objects.all().delete()
        cls.objects.bulk_create(batch)
        time1 = time()
        JournalEntry.log(None, "Updated bestof scores for %d users in %.1f seconds", len(batch), time1-time0)



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
            je = cls.objects.create(user=u, date=date, action=action)
            print(je)
        except Exception:
            cls.objects.create(user=None, action="Failed to log, based on format " + repr(fmt) +
                               " with args *" + repr(args) + " and kwargs **" +repr(kwargs))

    def __str__(self):
        n = self.user.email if self.user else "?"
        return ", ".join((n, self.date.isoformat(), self.action))


class AdminMessage(models.Model):
    network = models.ForeignKey(
        Network, null=True, default=None, on_delete=models.CASCADE
    )
    title = models.CharField(max_length=80, default="Message")
    message = models.CharField(max_length=280)

    def __str__(self):
        who = "Tout le monde" if self.network is None else "Réseau " + self.network.name
        return who + " : " + self.message
