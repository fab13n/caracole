"""
Draft of a new delivery description system. Typed.

Should be optimized for monogroup dv, but consolidable
in case of multiple networks on the same dv.

need to iterate in different ways:
* by user
* by product
* enumerated or not
"""

from typing import NamedTuple, Optional, List, TypeVar, Generic, Union, Any, Sequence, Dict, Tuple
from collections import defaultdict
from .. import models as m
from abc import ABC, abstractmethod
from functools import cached_property
from django.db.models import QuerySet
from decimal import Decimal

T = TypeVar("T")

class NetworkPurchase(object):
    """Total purchase of a given product by users of a given network.
    Intentionally matches a subset of m.Purchase's interface."""
    def __init__(self, network: m.Network, product: m.Product, quantity=Decimal(0)):
        self.network_id = network.id
        self.network = network
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


PurchaseType = Union[m.Purchase, NetworkPurchase]

class BaseRow(object):
    """Rows can be indexed by user or by network.
    Their purchases can therefore be of type m.Purchase or NetworkPurchase,
    but both types share a mostly common interface."""
    def __init__(self,
        purchases: List[Optional[PurchaseType]]):
        self.purchases = purchases

    @cached_property
    def packages(self) -> int: 
        return sum(
            pc.packages
            for pc in self.purchases
            if pc is not None
            and pc.product.quantity_per_package is not None
        )
    
    @cached_property
    def weight(self) ->float:
        return sum(
            pc.weight
            for pc in self.purchases
            if pc is not None
        )
    
    @cached_property
    def price(self) -> float:
        return sum(
            pc.price
            for pc in self.purchases
            if pc is not None
        )


class UserRow(BaseRow):
    def __init__(self,
        user: m.User, 
        purchases: List[Optional[m.Purchase]]):
        self.user_id = user.id
        self.user = user
        super().__init__(purchases)


class NetworkRow(BaseRow):
    def __init__(self,
        network: m.Network,
        purchases: List[Optional[NetworkPurchase]]):
        self.network_id = network.id
        self.network = network
        super().__init__(purchases)


class Column(object):
    """All purchases of a given product,
    either each user of a network, or each network of a delivery."""
    def __init__(self,
        product: m.Product,
        purchases: List[Optional[PurchaseType]]):

        assert all(pc.product_id == product.id for pc in purchases if pc is not None)
        self.product = product
        self.purchases = purchases

    @cached_property
    def quantity(self) -> float: 
        return sum(
            pc.quantity
            for pc in self.purchases
            if pc is not None)

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
        return sum(
            pc.weight
            for pc in self.purchases
            if pc is not None)
 
    @cached_property
    def price(self) -> float:
        return sum(
            pc.price
            for pc in self.purchases
            if pc is not None)


def _num(n):
    return None if n is None else float(n)

class NetworkDeliveryDescription(object):
    """Detailed description of the purchases of each member of a network
    for a given delivery. Might be created standalone, or as a part of
    a multi-network delivery description of type `DeliveryDescription`."""

    def __init__(
        self,
        dv: m.Delivery,
        network: m.Network,
        products: Optional[List[m.Product]] = None,
        matrix: Optional[Dict[Tuple[int, int], m.Purchase]] = None,
        empty_products=False,
        empty_users=False
        ):
 
        self.delivery = dv
        self.network = network

        # Remove users who aren't in the selected networks
        if empty_users:
            self.users = network.members.all()
        else:
            self.users = network.members.filter(purchase__product__delivery__in=[dv]).distinct()

        self.users = self.users.order_by('last_name', 'first_name')

        if products:
            self.products = products
        elif empty_products:
            self.products = dv.product_set.all().order_by('place')
        else:
            self.products = m.Product.objects \
                .filter(purchase__product__delivery__in=[dv]) \
                .distinct() \
                .order_by('place')

        # matrix: {tuple(user_id, product_id) -> m.Purchase}
        # When called from a DeliveryDescription, the matrix is pre-computed by the caller
        if matrix is None:
            matrix = defaultdict(lambda: None)
            # Thanks to defaultdict, access to absent purchases will return None
            for pd in self.products:
                for pc in m.Purchase.objects.filter(product=pd):
                    matrix[(pc.user_id, pc.product_id)] = pc

        # Reference by rows (user or nested description)
        self.rows: List[UserRow] = [
            UserRow(u, [matrix[(u.id, pd.id)] for pd in self.products]) 
            for u in self.users]

        # Reference by columns (products)
        self.columns: List[Column] = [
            Column(pd, [matrix[(u.id, pd.id)] for u in self.users]) 
            for pd in self.products]

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
        return {
            'delivery': {
                'id': self.delivery.id,
                'name': self.delivery.name
            },
            'network': {
                    'id': self.network.id,
                    'name': self.network.name
            },
            'products': [{  # TODO I'd still like to keep totals!
                'id': col.product.id,
                'name': col.product.name,
                'quantity_per_package': _num(col.product.quantity_per_package),
                'unit_weight': _num(col.product.unit_weight),
                'unit': col.product.unit,
                'price': _num(col.product.price),
                'total': {
                    'quantity': _num(col.quantity),
                    'packages': _num(col.packages), 
                    'out_of_package': _num(col.out_of_package),
                    'price': _num(col.price),
                    'weight': _num(col.weight),
                }
            } for col in self.columns],
            'users': [{
                'id': row.user.id,
                'first_name': row.user.first_name,
                'last_name': row.user.last_name,
                'email': row.user.email,
                'total': {
                    'packages': _num(row.packages),
                    'price': _num(row.price),
                    'weight': _num(row.weight),
                }
            } for row in self.rows],
            'total': {
                'packages': _num(self.packages),
                'price': _num(self.price),
                'weight': _num(self.weight)
            },
            'purchases': [
                [
                    {
                        'user': pc.user_id,
                        'product': pc.product_id,
                        'quantity': _num(pc.quantity),
                        'packages': _num(pc.packages) if pc.packages is not None else None, 
                        'out_of_package': _num(pc.out_of_package),
                        'price': _num(pc.price),
                        'weight': _num(pc.weight),
                    } if pc is not None else None for pc in row.purchases 
                ] for row in self.rows
            ]
        }


class DeliveryDescription(object):
    def __init__(
        self,
        dv: m.Delivery,
        empty_products=False,
        empty_users=False
        ):
 
        self.delivery = dv

        if empty_products:
            self.products = dv.product_set.all().order_by('place')
        else:
            self.products = m.Product.objects \
                .filter(purchase__product__delivery__in=[dv]) \
                .distinct() \
                .order_by('place')

        networks = dv.networks.all()

        # We need to give a network to each user. In theory they may have several,
        # we pick one arbitrarily.
        user_network: Dict[int, int] = {}  # user_id -> network_id
        for nw in networks:
            for u in nw.members.all().values('id'):
                user_network[u['id']] = nw.id

        # {network_id -> {tuple(user_id, product_id) -> purchase}}
        user_matrices: Dict[int, Dict[Tuple[int, int], Optional[m.Purchase]]] = \
            defaultdict(lambda: defaultdict(lambda: None))

        # {tuple(network_id, product_id) -> network_purchase}
        network_matrix: Dict[Tuple[int, int], NetworkPurchase] = {
            (nw.id, pd.id): NetworkPurchase(nw, pd)
            for nw in networks
            for pd in self.products}

        # {nw_id -> [NetworkPurchase*]}
        network_purchases: Dict[int, List[NetworkPurchase]] = {
            nw.id: [NetworkPurchase(nw, pd) for pd in self.products]
            for nw in networks
        }

        for i, pd in enumerate(self.products):
            for pc in m.Purchase.objects.filter(product=pd):
                nw_id = user_network[pc.user_id]
                user_matrices[nw_id][(pc.user_id, pc.product_id)] = pc
                network_matrix[(nw_id, pc.product_id)].add(pc)
                network_purchases[nw_id][i].add(pc)

        self.network_descriptions: List[NetworkDeliveryDescription] = [
            NetworkDeliveryDescription(
                dv, nw, 
                products=self.products, 
                matrix=user_matrices[nw.id],
                empty_users=empty_users
            ) for nw in networks
        ]

        # Reference by rows (user or nested description)
        self.rows: List[NetworkRow] = [
            NetworkRow(nw, network_purchases[nw.id])
            for nw in networks]

        # Reference by columns (products)
        self.columns: List[NetworkColumn] = [
            Column(pd, [network_matrix[(nw.id, pd.id)] for u in networks]) 
            for pd in self.products]

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
            'delivery': {
                'id': self.delivery.id,
                'name': self.delivery.name
            },
            'products': [{
                'id': col.product.id,
                'name': col.product.name,
                'quantity_per_package': _num(col.product.quantity_per_package),
                'unit_weight': _num(col.product.unit_weight),
                'unit': col.product.unit,
                'price': _num(col.product.price),
                'total': {
                    'quantity': _num(col.quantity),
                    'packages': _num(col.packages),
                    'out_of_package': _num(col.out_of_package),
                    'price': _num(col.price),
                    'weight': _num(col.weight),
                }
            } for col in self.columns],
            'networks': [
                self.network_descriptions[i].to_json()
                for i, row in enumerate(self.rows)],
            'total': {
                'packages': _num(self.packages),
                'price': _num(self.price),
                'weight': _num(self.weight)
            },
            'purchases': [
                [
                    {
                        'product': pc.product_id,
                        'network': row.network_id,
                        'quantity': _num(pc.quantity),
                        'packages': _num(pc.packages), 
                        'out_of_package': _num(pc.out_of_package),
                        'price': _num(pc.price),
                        'weight': _num(pc.weight),
                    } if pc.quantity > 0 else None for pc in row.purchases 
                ] for row in self.rows
            ]
        }
