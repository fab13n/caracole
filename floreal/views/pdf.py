#!/usr/bin/python
# -*- coding: utf8 -*-

"""PDF views generator."""

from pyfpdf import FPDF, HTMLMixin

from .. import models as m
from .delivery_description import delivery_description

DATABASE_UTF8_ENABLED = False


def _u8(s):
    """Convert DB contents into UTF8 if necessary."""
    return unicode(s) if DATABASE_UTF8_ENABLED else str(s).decode('utf-8')


class CardsDeck(FPDF, HTMLMixin):

    # FULL_PAGES = False # Half pages
    FULL_PAGES = True # Full pages

    def __init__(self):
        # HTMLMixin.__init__(self) # No constructor
        # super(UserCardsDeck, self).__init__()  # FPDF is an old-style class
        FPDF.__init__(self)

    def _print(self, utxt):
        # Latin1 / Latin9 don't seem able to cope with Euro sign
        self.write_html(utxt.replace(u'€', u'EUR').encode('latin9'))
        # self.write_html(utxt.replace(u'€', chr(128)).encode('latin9'))

    def _jump_to_next_order(self):
        """Start the next user card: either go to the 2nd half of the current page,
        or to the top of a new page."""
        try:
            if self.get_y() > self.h/2 or self.FULL_PAGES:
                self.add_page()
            else:
                self.set_y(self.h/2);
                self._print(u"<hr/>")
        except:
            self.add_page()


class SubgroupCardsDeck(CardsDeck):

    FULL_PAGES = True

    def __init__(self, title, dv, subgroups):
        CardsDeck.__init__(self)
        descr = delivery_description(dv, subgroups)
        for table in descr['table']:
            self._print_subgroup_card(title, table)

    def _print_subgroup_item(self, totals):
        qty = totals['quantity']
        pd = totals['product']
        values = {
            'granted': qty,
            'unit': pd.unit,
            'prod_name': m.articulate(pd.name),
            'price': pd.price * qty}
        if pd.quantity_per_package and qty >= pd.quantity_per_package:
            values.update({
              'packages': qty // pd.quantity_per_package,
              'loose': qty % pd.quantity_per_package
            })
            if values['loose']:  # Some loose items
                r = u"%(packages)g cartons plus %(loose)s %(unit)s %(prod_name)s" % values
            else:  # Round number of packages
                r = u"%(packages)g cartons %(prod_name)s" % values
        else:  # Unpackaged product
            r = u"%(granted)g %(unit)s %(prod_name)s" % values
        if pd.unit_weight and (pd.unit != 'kg' or 'packages' in values):
            r += u" (%s kg)" % (float(qty)*float(pd.unit_weight))
        return r

    def _print_subgroup_card(self, title, table):
        items = u''.join([u"<li>%s</li>" % self._print_subgroup_item(t) for t in table['totals'] if t['quantity']])
        if items:
            self._jump_to_next_order()
            self._print(u"""
                    <h1>Commande %(u)s: %(price).02f€, %(weight)s kg</h1>
                    <h2>%(title)s</h2>
                    <ul>%(od)s</ul>""" % {
                    'u': m.articulate(table['subgroup'].name),
                    'price': table['price'],
                    'weight': table['weight'],
                    'title': title,
                    'od': items})


class UserCardsDeck(SubgroupCardsDeck):

    # FULL_PAGES = False # Half pages
    FULL_PAGES = True # Full pages

    def __init__(self, title, delivery, sg):
        CardsDeck.__init__(self)
        users = sg.sorted_users
        orders = m.Order.by_user_and_product(delivery, users)

        descr = delivery_description(delivery, [sg])
        self._print_subgroup_card(title, descr['table'][0])

        self._print_price_sheet(delivery)

        for u in users:
            od = orders[u]  # Don't iterate directly on orders, it wouldn't preserve order
            self._print_user_card(od, title)

    def _print_price_sheet(self, dv):
        self._jump_to_next_order()
        prices = [u'<li>%s: %.02f€/%s</li>' % (pd.name, pd.price, pd.unit) for pd in dv.product_set.all()]
        self._print(u'<h1>Prix des produits</h1><ul>%s</ul>' % ''.join(prices))

    def _print_user_item(self, pc):
        return u"""<tr>
            <td>%(name)s</td>
            <td>%(u_price).02f€</td>
            <td>%(ordered_qty)s %(unit)s</td>
            <td>%(ordered_price).02f€</td>
            <td>_</td>
            <td>_</td>
        </tr>
        """ % {
            'name': pc.product.name,
            'u_price': pc.product.price,
            'unit': pc.product.unit,
            'ordered_qty': pc.ordered,
            'ordered_price': pc.price,
        }

    def _print_user_card(self, od, title):
        items = u''.join(self._print_user_item(pc) for pc in od.purchases if pc)
        if items:
            extra_line = "<tr><td>_</td><td>_</td><td> </td><td> </td><td>_</td><td>_</td></tr>\n"
            self._jump_to_next_order()
            self._print(u"""
                    <h1>Commande %(u)s: %(total).02f€</h1>
                    <h2>%(title)s</h2>
                    <table border="1" align="center" width="100%%">
                      <thead>
                        <tr>
                          <th width="40%%">Produit</th>
                          <th width="10%%">Prix U.</th>
                          <th width="15%%">Commandé</th>
                          <th width="10%%">Commandé</th>
                          <th width="15%%">Modif.</th>
                          <th width="10%%">Prix mod.</th>
                        </tr>
                      </thead>
                      <tbody>
                        %(items)s
                        %(extra)s
                      </tbody>
                      <thead>
                        <tr>
                          <td colspan="3">Total</td>
                          <td>%(total).02f€</td>
                          <td> </td>
                          <td>_</td>
                        </tr>
                      </thead>
                    </table>
                    """ % {
                    'u': m.articulate(od.user.first_name + " " + od.user.last_name),
                    'total': od.price,
                    'title': title,
                    'items': items,
                    'extra': extra_line * 3})


def subgroup(delivery, sg):
    """Generate a PDF of every user order in this delivery for this subgroup"""
    title = "%(nw)s / %(dv)s / %(sg)s" % {'nw': delivery.network.name,
                                          'dv': delivery.name,
                                          'sg': sg.name}
    pdf = UserCardsDeck(title, delivery, sg)
    return pdf.output(dest='S')


def all(delivery):
    """Generate a PDF of every subgroup in this delivery"""
    title = "%(nw)s / %(dv)s" % {'nw': delivery.network.name,
                                 'dv': delivery.name}
    all_subgroups = m.Subgroup.objects.filter(network=delivery.network)
    pdf = SubgroupCardsDeck(title, delivery, all_subgroups)
    return pdf.output(dest='S')
