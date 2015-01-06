"""PDF views generator."""

from pyfpdf import FPDF, HTMLMixin
from . import models as m


class UserCardsDeck(FPDF, HTMLMixin):

    def __init__(self, delivery, subgroup):
        super(UserCardsDeck, self).__init__()
        users = m.User.objects.filter(user_of__in=[subgroup]).order_by('last_name', 'first_name')
        orders = m.Order.by_user_and_product(delivery, users)
        for od in orders:
            self._print_order(od, subgroup)

    def _print_order(self, od, sg):

        items = ["<li>"+pc.__unicode__(specify_user=False)+"</li>"
                 for pc in od.purchases if pc]

        if items:
            self._jump_to_next_order()
            self.write_html("""
                    <h1>Commande %(u)s</h1>
                    <h2>%(nw)s / %(dv)s / %(sg)s</h2>
                    <ul>%(od)s</ul>""" % {
                    'u': m.articulate(od.user.first_name + " " + od.user.last_name),
                    'nw': od.delivery.network.name,
                    'dv': od.delivery.name,
                    'sg': sg.name,
                    'od': ''.join(items)})

    def _jump_to_next_order(self):
        """Start the next user card: either go to the 2nd half of the current page,
        or to the top of a new page."""
        try:
            if self.get_y() > self.h/2:
                self.add_page()
            else:
                self.set_y(self.h/2);
                self.write_html("<hr/>")
        except:
            self.add_page()


def subgroup(delivery, subgroup):
    """Generate a PDF of every user order in this delivery for this subgroup"""
    pdf = UserCardsDeck(delivery, subgroup)
    return pdf.output(dest='S')
