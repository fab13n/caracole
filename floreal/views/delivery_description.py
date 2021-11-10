"""
Draft of a new delivery description system. Typed.

Should be optimized for monogroup dv, but consolidable
in case of multiple networks on the same dv.

need to iterate in different ways:
* by user
* by product
* enumerated or not
"""

from typing import (
    NamedTuple,
    Optional,
    List,
    TypeVar,
    Generic,
    Union,
    Any,
    Sequence,
    Dict,
    Tuple,
)
from collections import defaultdict
from .. import models as m
from abc import ABC, abstractmethod
from functools import cached_property
from django.db.models import QuerySet, Q
from django.db.models.functions import Lower
from decimal import Decimal


T = TypeVar("T")

def img_url(image_field: Optional[m.models.ImageField]):
    return image_field.url if image_field else None

class SubgroupPurchase(object):
    """
    Total purchase of a given product by users of a given network subgroup.
    Intentionally matches a subset of models.Purchase's interface.
    """

    def __init__(
        self, subgroup: m.NetworkSubgroup, product: m.Product, quantity=Decimal(0)
    ):
        self.subgroup_id = subgroup.id
        self.subgroup = subgroup
        self.product_id = product.id
        self.product = product
        self.quantity = quantity

    def add(self, pc: m.Purchase):
        self.quantity += pc.quantity  # TODO make quantity a decimal, rather

    @cached_property
    def out_of_package(self) -> float:
        if self.product.quantity_per_package is None:
            return self.quantity
        else:
            return self.quantity - self.packages * self.product.quantity_per_package

    @cached_property
    def packages(self) -> Optional[int]:
        if self.product.quantity_per_package is None:
            return None
        else:
            return self.quantity // self.product.quantity_per_package

    @cached_property
    def weight(self) -> float:
        return self.product.unit_weight * self.quantity

    @cached_property
    def price(self) -> float:
        return self.product.price * self.quantity


PurchaseType = Union[m.Purchase, SubgroupPurchase]


class BaseRow(object):
    """Rows can be indexed by user or by subgroup.
    Their purchases can therefore be of type m.Purchase or NetworkPurchase,
    but both types share a mostly common interface."""

    def __init__(self, purchases: List[Optional[PurchaseType]]):
        self.purchases = purchases

    @cached_property
    def packages(self) -> int:
        return sum(
            pc.packages
            for pc in self.purchases
            if pc is not None and pc.product.quantity_per_package is not None
        )

    @cached_property
    def weight(self) -> float:
        return sum(pc.weight for pc in self.purchases if pc is not None)

    @cached_property
    def price(self) -> float:
        return sum(pc.price for pc in self.purchases if pc is not None)


class UserRow(BaseRow):
    def __init__(self, user: m.User, purchases: List[Optional[m.Purchase]]):
        self.user_id = user.id
        self.user = user
        super().__init__(purchases)


class SubgroupRow(BaseRow):
    def __init__(
        self, subgroup: m.NetworkSubgroup, purchases: List[Optional[SubgroupPurchase]]
    ):
        self.subgroup_id = subgroup.id
        self.subgroup = subgroup
        super().__init__(purchases)


class Column(object):
    """
    All purchases of a given product,
    either each user or each subgroup of a network.
    """

    def __init__(self, product: m.Product, purchases: List[Optional[PurchaseType]]):

        assert all(pc.product_id == product.id for pc in purchases if pc is not None)
        self.product = product
        self.purchases = purchases

    @cached_property
    def quantity(self) -> float:
        return sum(pc.quantity for pc in self.purchases if pc is not None)

    @cached_property
    def out_of_package(self) -> float:
        if self.product.quantity_per_package is None:
            return self.quantity
        else:
            return self.quantity - self.packages * self.product.quantity_per_package

    @cached_property
    def packages(self) -> Optional[int]:
        if self.product.quantity_per_package is None:
            return None
        else:
            return self.quantity // self.product.quantity_per_package

    @cached_property
    def weight(self) -> float:
        return sum(pc.weight for pc in self.purchases if pc is not None)

    @cached_property
    def price(self) -> float:
        return sum(pc.price for pc in self.purchases if pc is not None)


def _num(n):
    return None if n is None else float(n)


class FlatDeliveryDescription(object):
    """
    Detailed description of the purchases of each member of a network
    for a given delivery. Might be created standalone, or as a part of
    a multi-network delivery description of type `GroupedDeliveryDescription`.

    TODO: we should probbaly just have a function producing some JSON, rather than an intermediate class instance with to_json()
    """

    def __init__(
        self,
        dv: m.Delivery,
        subgroup: Optional[m.NetworkSubgroup] = None,
        products: Optional[List[m.Product]] = None,
        matrix: Optional[Dict[Tuple[int, int], m.Purchase]] = None,
        users: Optional[List[m.User]] = None,
        empty_products=False,
        empty_users=False,
    ):

        self.delivery = dv
        self.network = dv.network
        self.subgroup = subgroup

        # Remove users who aren't in the selected network / subgroup
        if users is not None:
            self.users = users
        else:
            args = [
                Q(networkmembership__valid_until=None),
                Q(networkmembership__network_id=dv.network_id),
                Q(networkmembership__is_buyer=True)
            ]
            date = dv.freeze_date
            if date is not None:
                args +=[
                    Q(networkmembership__valid_until__gte=date)|
                    Q(networkmembership__valid_until=None),
                    Q(networkmembership__valid_from__lte=date)
                ]
            else:
                args += [
                    Q(networkmembership__valid_until=None)
                ]
           
            if subgroup is not None:
                args += [
                    Q(networkmembership__subgroup_id=subgroup.id)
                ]
            self.users = (m.User.objects
                .filter(*args)
                .order_by(Lower("last_name"), Lower("first_name"))
            )
            # Remove those who didn't order
            if not empty_users:
                self.users = self.users.filter(
                    purchase__product__delivery__in=[dv]
                ).distinct()
            # Sort what's left
            self.users = self.users.order_by("last_name", "first_name")

        if products:
            self.products = products
        elif empty_products:
            self.products = dv.product_set.all().order_by("place")
        else:
            self.products = (
                m.Product.objects.filter(purchase__product__delivery__in=[dv])
                .distinct()
                .order_by("place")
            )

        # matrix: {tuple(user_id, product_id) -> m.Purchase}
        # When called from a GroupedDeliveryDescription, the matrix is pre-computed by the caller
        if matrix is None:
            matrix = defaultdict(lambda: None)
            for pc in m.Purchase.objects.filter(product__delivery_id=dv.id).select_related("product"):
                matrix[(pc.user_id, pc.product_id)] = pc

        # Reference by rows (user or nested description)
        self.rows: List[UserRow] = [
            UserRow(u, [matrix[(u.id, pd.id)] for pd in self.products])
            for u in self.users
        ]

        # Reference by columns (products)
        self.columns: List[Column] = [
            Column(pd, [matrix[(u.id, pd.id)] for u in self.users])
            for pd in self.products
        ]

    @cached_property
    def packages(self) -> int:
        return sum(c.packages or 0 for c in self.columns)

    @cached_property
    def weight(self) -> float:
        return sum(c.weight for c in self.columns)

    @cached_property
    def price(self) -> int:
        return sum(c.price for c in self.columns)

    def to_json(self, nested=False):
        r = {
            "delivery": {
                "id": self.delivery.id,
                "name": self.delivery.name,
                "freeze": str(d) if (d:=self.delivery.freeze_date) is not None else None,
                "distribution": str(d) if (d:=self.delivery.distribution_date) is not None else None,
                "state": self.delivery.state,
                "state_name": self.delivery.state_name(),
            },
            "network": {"id": self.network.id, "name": self.network.name},
            "subgroup": None
            if self.subgroup is None
            else {"id": self.subgroup.id, "name": self.subgroup.name},
            "products": [
                {
                    "id": col.product.id,
                    "name": col.product.name,
                    "quantity_per_package": _num(col.product.quantity_per_package),
                    "unit_weight": _num(col.product.unit_weight),
                    "unit": col.product.unit,
                    "price": _num(col.product.price),
                    "plurals": {"name": m.plural(col.product.name), "unit": m.plural(col.product.unit)},
                    "total": {
                        "quantity": _num(col.quantity),
                        "packages": _num(col.packages),
                        "out_of_package": _num(col.out_of_package),
                        "price": _num(col.price),
                        "weight": _num(col.weight),
                    },
                }
                for col in self.columns
            ],
            "users": [
                {
                    "id": row.user.id,
                    "first_name": row.user.first_name,
                    "last_name": row.user.last_name,
                    "email": row.user.email,
                    "total": {
                        "packages": _num(row.packages),
                        "price": _num(row.price),
                        "weight": _num(row.weight),
                    },
                }
                for row in self.rows
            ],
            "total": {
                "packages": _num(self.packages),
                "price": _num(self.price),
                "weight": _num(self.weight),
            },
            "purchases": [
                [
                    {
                        "user": pc.user_id,
                        "product": pc.product_id,
                        "quantity": _num(pc.quantity),
                        "packages": _num(pc.packages)
                        if pc.packages is not None
                        else None,
                        "out_of_package": _num(pc.out_of_package),
                        "price": _num(pc.price),
                        "weight": _num(pc.weight),
                    }
                    if pc is not None
                    else None
                    for pc in row.purchases
                ]
                for row in self.rows
            ],
        }
        return r


# TODO: convert into subgrouped-dd
class GroupedDeliveryDescription(object):
    def __init__(self, dv: m.Delivery, empty_products=False, empty_users=False):

        self.delivery = dv

        if empty_products:
            self.products = dv.product_set.all()
        else:
            self.products = m.Product.objects.filter(
                purchase__product__delivery__in=[dv]
            ).distinct()
        self.products = list(
            self.products.prefetch_related("purchase_set").order_by("place")
        )

        subgroups = dv.network.networksubgroup_set.all()

        subgroup_users: Dict[int, List[m.User]] = defaultdict(list)  # sgid -> [User*]
        user_subgroup: Dict[int, int] = {}  # user_id -> subgroup_id
        for nm in (
            m.NetworkMembership.objects.filter(network_id=dv.network_id, is_buyer=True, valid_until=None)
            .select_related("user")
            .order_by("user__last_name", "user__first_name")
        ):
            sg_id = nm.subgroup_id
            if sg_id is not None:
                subgroup_users[sg_id].append(nm.user)
                user_subgroup[nm.user_id] = sg_id

        # {subgroup_id -> {tuple(user_id, product_id) -> purchase}}
        user_matrices: Dict[
            int, Dict[Tuple[int, int], Optional[m.Purchase]]
        ] = defaultdict(lambda: defaultdict(lambda: None))

        # {tuple(subgroup_id, product_id) -> subgroup_purchase}
        subgroup_matrix: Dict[Tuple[int, int], SubgroupPurchase] = {
            (sg.id, pd.id): SubgroupPurchase(sg, pd)
            for sg in subgroups
            for pd in self.products
        }

        # {sg_id -> [SubgroupPurchase*]}
        subgroup_purchases: Dict[int, List[SubgroupPurchase]] = {
            sg.id: [SubgroupPurchase(sg, pd) for pd in self.products]
            for sg in subgroups
        }

        product_index = {pd.id: i for (i, pd) in enumerate(self.products)}

        # Prefetch products, needed to compute purchase prices, weights etc.
        for pc in m.Purchase.objects.filter(product__delivery_id=dv.id).select_related("product"):
            sg_id = user_subgroup.get(pc.user_id)
            pd_id = pc.product_id
            u_id = pc.user_id
            if sg_id is None:
                # print(f"Warning: {pc.user.username} left {dv.network.name}")
                continue
            user_matrices[sg_id][(u_id, pd_id)] = pc
            subgroup_matrix[(sg_id, pd_id)].add(pc)
            subgroup_purchases[sg_id][product_index[pd_id]].add(pc)

        self.subgroup_descriptions: List[FlatDeliveryDescription] = [
            FlatDeliveryDescription(
                dv,
                subgroup=sg,
                products=self.products,
                users=subgroup_users[sg.id],
                matrix=user_matrices[sg.id],
                empty_users=empty_users,
            )
            for sg in subgroups
        ]

        # Reference by rows (user or nested description)
        self.rows: List[SubgroupRow] = [
            SubgroupRow(sg, subgroup_purchases[sg.id]) for sg in subgroups
        ]

        # Reference by columns (products)
        self.columns: List[Column] = [
            Column(pd, [subgroup_matrix[(sg.id, pd.id)] for sg in subgroups])
            for pd in self.products
        ]

    @cached_property
    def packages(self) -> int:
        return sum(c.packages or 0 for c in self.columns)

    @cached_property
    def weight(self) -> float:
        return sum(c.weight for c in self.columns)

    @cached_property
    def price(self) -> int:
        return sum(c.price for c in self.columns)

    def to_json(self):
        return {
            "delivery": {
                "id": self.delivery.id,
                "name": self.delivery.name,
                "freeze": str(d) if (d:=self.delivery.freeze_date) is not None else None,
                "distribution": str(d) if (d:=self.delivery.distribution_date) is not None else None,
                "state": self.delivery.state,
                "state_name": self.delivery.state_name(),
            },
            "network": {
                "id": self.delivery.network.id,
                "name": self.delivery.network.name,
            },
            "products": [
                {
                    "id": col.product.id,
                    "name": col.product.name,
                    "quantity_per_package": _num(col.product.quantity_per_package),
                    "unit_weight": _num(col.product.unit_weight),
                    "unit": col.product.unit,
                    "price": _num(col.product.price),
                    "plurals": {"name": m.plural(col.product.name), "unit": m.plural(col.product.unit)},
                    "total": {
                        "quantity": _num(col.quantity),
                        "packages": _num(col.packages),
                        "out_of_package": _num(col.out_of_package),
                        "price": _num(col.price),
                        "weight": _num(col.weight),
                    },
                }
                for col in self.columns
            ],
            "subgroups": [
                self.subgroup_descriptions[i].to_json()
                for i, row in enumerate(self.rows)
            ],
            "total": {
                "packages": _num(self.packages),
                "price": _num(self.price),
                "weight": _num(self.weight),
            },
            "purchases": [
                [
                    {
                        "product": pc.product_id,
                        "subgroup": row.subgroup_id,
                        "quantity": _num(pc.quantity),
                        "packages": _num(pc.packages),
                        "out_of_package": _num(pc.out_of_package),
                        "price": _num(pc.price),
                        "weight": _num(pc.weight),
                    }
                    if pc.quantity > 0
                    else None
                    for pc in row.purchases
                ]
                for row in self.rows
            ],
        }


class UserDeliveryDescription(object):

    def __init__(self, dv: m.Delivery, u: m.User, empty_products=False):

        self.user = u
        self.delivery = dv
        self.network = dv.network

        purchases_by_pd_id = {
            pc.product_id: pc
            for pc in m.Purchase.objects.filter(product__delivery=dv, user=u).order_by(
                "product__place"
            )
        }

        if empty_products:
            # All products
            self.products = dv.product_set.all().order_by("place")
        else:
            # Only products with a purchase by this user
            self.products = [pc.product for pc in purchases_by_pd_id.values()]

        self.purchases = [purchases_by_pd_id.get(pd.id) for pd in self.products]
        self.price = sum(pc.price for pc in purchases_by_pd_id.values())
        self.weight = sum(pc.weight for pc in purchases_by_pd_id.values())

        # TODO Check SQL logs, probably a lack of select_related on purchase->product

    def to_json(self):
        return {
            "user": {
                "id": self.user.id,
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
            },
            "delivery": {
                "id": self.delivery.id,
                "name": self.delivery.name,
                "description": self.delivery.description,
                "freeze": str(d) if (d:=self.delivery.freeze_date) is not None else None,
                "distribution": str(d) if (d:=self.delivery.distribution_date) is not None else None,
                "state": self.delivery.state,
                "state_name": self.delivery.state_name(),
            },
            "network": {
                "id": self.network.id,
                "name": self.network.name,
                "description": self.network.description,
                "image_description": img_url(self.network.image_description),
            },
            "producer": {
                "name": prod.first_name + " " + prod.last_name,
                "description": prod.florealuser.description,
                "image_description": img_url(prod.florealuser.image_description),
            } if (prod := self.delivery.producer) else None,
            "products": [
                {
                    "id": pd.id,
                    "name": pd.name,
                    "quantity_per_package": _num(pd.quantity_per_package),
                    "unit_weight": _num(pd.unit_weight),
                    "unit": pd.unit,
                    "price": _num(pd.price),
                    "quantum": _num(pd.quantum),
                    "image": pd.image.url if pd.image else None,
                    "description": pd.description,
                    "plurals": {"name": m.plural(pd.name), "unit": m.plural(pd.unit)},
                    "purchase": {
                        "id": pc.id,
                        "quantity": _num(pc.quantity),
                        "packages": _num(pc.packages),
                        "out_of_package": _num(pc.out_of_package),
                        "price": _num(pc.price),
                        "weight": _num(pc.weight),
                        "max_quantity": _num(pd.left - pc.quantity)
                        if pd.left is not None
                        else None,
                    }
                    if pc is not None
                    else {
                        "id": None,
                        "quantity": 0,
                        "packages": 0 if pd.quantity_per_package is not None else None,
                        "out_of_package": 0,
                        "price": 0,
                        "weight": 0,
                        "max_quantity": _num(
                            None
                            if pd.left is None
                            else pd.left
                            if pc is None
                            else pd.left - pc.quantity
                        ),
                    },
                }
                for pd, pc in zip(self.products, self.purchases)
            ],
            "total": {
                "price": _num(self.price),
                "weight": _num(self.weight),
            },
        }
