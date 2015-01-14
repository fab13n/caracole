#!/usr/bin/python
# -*- coding: utf8 -*-

"""PDF views generator."""

from pyfpdf import FPDF, HTMLMixin

from .. import models as m


DATABASE_UTF8_ENABLED = False


def _u8(s):
    """Convert DB contents into UTF8 if necessary."""
    return unicode(s) if DATABASE_UTF8_ENABLED else str(s).decode('utf-8')


class UserCardsDeck(FPDF, HTMLMixin):

    def __init__(self, delivery, subgroup):
        # HTMLMixin.__init__(self) # No constructor
        # super(UserCardsDeck, self).__init__()  # FPDF is an old-style class
        FPDF.__init__(self)
        users = subgroup.sorted_users
        orders = m.Order.by_user_and_product(delivery, users)
        for od in orders.values():
            self._print_order(od, subgroup)

    def _print(self, utxt):
        # Latin1 / Latin9 don't seem able to cope with Euro sign
        self.write_html(utxt.replace(u'€', u'EUR').encode('latin9'))


    def _print_order(self, od, sg):

        items = u''.join([u"<li>%s</li>" % pc.__unicode__(specify_user=False) for pc in od.purchases if pc])

        if items:
            self._jump_to_next_order()
            self._print(u"""
                    <h1>Commande %(u)s: %(total).02f€</h1>
                    <h2>%(nw)s / %(dv)s / %(sg)s</h2>
                    <ul>%(od)s</ul>""" % {
                    'u': m.articulate(od.user.first_name + " " + od.user.last_name),
                    'total': od.price,
                    'nw': od.delivery.network.name,
                    'dv': od.delivery.name,
                    'sg': sg.name,
                    'od': items})

    def _jump_to_next_order(self):
        """Start the next user card: either go to the 2nd half of the current page,
        or to the top of a new page."""
        try:
            if self.get_y() > self.h/2:
                self.add_page()
            else:
                self.set_y(self.h/2);
                self._print(u"<hr/>")
        except:
            self.add_page()


def subgroup(delivery, sg):
    """Generate a PDF of every user order in this delivery for this subgroup"""
    pdf = UserCardsDeck(delivery, sg)
    return pdf.output(dest='S')
