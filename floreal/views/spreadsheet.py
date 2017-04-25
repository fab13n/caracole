#!/usr/bin/python
# -*- coding: utf8 -*-

"""Excel spreadsheet views generator."""

from StringIO import StringIO
import xlsxwriter as xls

from .delivery_description import delivery_description

DATABASE_UTF8_ENABLED = True
PROTECT_FORMULA_CELLS = False


def _u8(s):
    """Convert DB contents into UTF8 if necessary."""
    return unicode(s) if DATABASE_UTF8_ENABLED else str(s).decode('utf-8')


def _col_name(c):
    """Convert a zero-based index into an Excel column name."""
    if c < 26:
        return chr(65+c)
    elif c < 26*27:
        return chr(64+c/26) + chr(65+c%26)
    else:
        raise Exception("Too many products")


# By how much the first element of the 2D user/product quantity matrix is shifted
ROW_OFFSET = 12
COL_OFFSET = 6

V_CYCLE_LENGTH = 5
H_CYCLE_LENGTH = 5

def _make_sheet(book, title, fmt, buyers, products, purchases, purchase_fmls=None,
                group_recap=False, one_group=False, extra_line=0, extra_fmls=None):
    """
    :param buyers: ordered list of buyers
    :param products: ordered list of products
    :param purchases: function (buyer_idx, product_idx) -> quantity
    :return:
    """
    extra_line = 1 if extra_line else 0  # Force int value for easy additions
    sheet = book.add_worksheet(title)
    if PROTECT_FORMULA_CELLS:
        sheet.protect()
    sheet.set_column(0, 0, 30)
    sheet.set_column(1, 1, 12)
    sheet.set_row(0, 75)
    sheet.set_row(2, 50)
    sheet.merge_range('A1:J1', u"Achats du réseau %s:\n%s pour %s" % (
        products[0].delivery.network.name, title, products[0].delivery.name), fmt['title'])
    for row, title in enumerate([u"Prix unitaire", u"Poids unitaire", u"Nombre par carton",
                                 u"Nombre de pièces", u"Nombre de cartons", u"Nombre en complément",
                                 u"Poids total"]):
        sheet.merge_range('B%d:E%d'%(row+4, row+4), title, fmt['hdr_title_right'])
    for r in range(3, 12):
        sheet.write_blank(r, COL_OFFSET-1, None, fmt['hdr_blank'])
    sheet.write(2, COL_OFFSET-1, u"Prix\n&\nTotaux", fmt['hdr_title'])
    sheet.write(10, 1, u"Espèces", fmt['hdr_title'])
    sheet.write(10, 2, u"Chèque", fmt['hdr_title'])
    sheet.write(10, 3, u"Avoir", fmt['hdr_title'])
    sheet.write(10, 4, u"Dû", fmt['hdr_title'])

    # Generate product names and prices rows
    if group_recap or one_group:
        # Product descriptions are written directly here, not taken from mainpage
        for c, pd in enumerate(products):
            # python row / Excel row: content
            # 2/3: Name
            # 3/4: Unit price
            # 4/5: Unit weight
            # 5/6: per package
            # 6/7: # units
            # 7/8: # full ackages
            # 8/9: # lose units
            # 9/10: total weight
            # 10/11: total price (1 cell)
            sheet.write(2, c+COL_OFFSET, _u8(pd.name), fmt['pd_name'])
            sheet.write(3, c+COL_OFFSET, pd.price, fmt['hdr_price'])
            sheet.write(4, c+COL_OFFSET, pd.unit_weight, fmt['hdr_weight'])
            sheet.write(5, c+COL_OFFSET, pd.quantity_per_package or "-", fmt['hdr_qty'])
    else:
        # In subgroup sheets, recopy product descriptions from 1st page
        for c, pd in enumerate(products):
            fml = "=Commande!%(col)s%%s" % {'col': _col_name(c+COL_OFFSET)}
            sheet.write(2, c+COL_OFFSET, fml % 3, fmt['pd_name'], _u8(pd.name))
            sheet.write(3, c+COL_OFFSET, fml % 4, fmt['hdr_price'], pd.price)
            sheet.write(4, c+COL_OFFSET, fml % 5, fmt['hdr_weight'], pd.unit_weight)
            sheet.write(5, c+COL_OFFSET, fml % 6, fmt['hdr_qty'], pd.quantity_per_package)

    n_products = len(products)
    n_buyers = len(buyers)
    price_buyer = [0] * (n_buyers+extra_line)
    weight_buyer = [0] * (n_buyers+extra_line)
    qty_buyer = [0] * (n_buyers+extra_line)
    qty_product = [0] * n_products
    weight_product = [0] * n_products

    # Generate buyer names column.
    for r, name in enumerate(buyers):
        fmt_u = fmt['user_name_cycle'] if r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1 else fmt['user_name']
        sheet.write(r+ROW_OFFSET, 0, _u8(name), fmt_u)
    if extra_line:
        sheet.write(n_buyers + ROW_OFFSET, 0, "Extra", fmt['user_name_cycle'])

    # Fill purchases, count totals
    for c, pd in enumerate(products):
        h_cycle = c % H_CYCLE_LENGTH == H_CYCLE_LENGTH - 1
        for r in range(n_buyers):
            qty = purchases(r, c)
            v_cycle = r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1
            if h_cycle and v_cycle:
                fmt_name = 'qty_vh_cycle'
            elif h_cycle:
                fmt_name = 'qty_h_cycle'
            elif v_cycle:
                fmt_name = 'qty_v_cycle'
            else:
                fmt_name = 'qty'

            if purchase_fmls:
                fml = purchase_fmls(r, c)
                sheet.write(r+ROW_OFFSET, c+COL_OFFSET, fml, fmt['f_'+fmt_name], qty)
            else:
                sheet.write(r+ROW_OFFSET, c+COL_OFFSET, qty, fmt[fmt_name])
            qty_buyer[r] += qty
            qty_product[c] += qty
            price_buyer[r] += qty * pd.price
            if pd.unit_weight:
                w = qty * pd.unit_weight
                weight_buyer[r] += w
                weight_product[c] += w
        if extra_line:
            fmt_x = fmt['qty_vh_cycle' if h_cycle else 'qty_v_cycle']
            if extra_fmls:
                fml = extra_fmls(n_buyers, c)
                sheet.write(n_buyers+ROW_OFFSET, c+COL_OFFSET, fml, fmt_x, 0)
            else:
                sheet.write(n_buyers+ROW_OFFSET, c+COL_OFFSET, 0, fmt_x)

    # Total price per buyer, plus accounting columns cheque / especes / avoir / du
    for r in range(n_buyers):
        fml = "=SUMPRODUCT(" \
              "%(firstcol)s$%(u_price_row)s:%(lastcol)s$%(u_price_row)s," \
              "%(firstcol)s%(qty_row)s:%(lastcol)s%(qty_row)s)" % \
              {'firstcol': _col_name(COL_OFFSET),
               'lastcol': _col_name(n_products+COL_OFFSET-1),
               'u_price_row': 4,  # unit price
               'qty_row': r+ROW_OFFSET+1}
        fmt_p = fmt['hdr_user_price_cycle'] if r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1 else fmt['hdr_user_price']
        sheet.write(r+ROW_OFFSET, COL_OFFSET-1, fml, fmt_p, price_buyer[r])
        fmt_p = fmt['price_h_cycle'] if r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1 else fmt['price']
        if group_recap:
            # Retrieve values from other pages' totals
            fml = "=%s!%%s12" % (buyers[r])
            sheet.write(r+ROW_OFFSET, 1, fml % 'B', fmt_p, 0)
            sheet.write(r+ROW_OFFSET, 2, fml % 'C', fmt_p, 0)
            sheet.write(r+ROW_OFFSET, 3, fml % 'D', fmt_p, 0)
            sheet.write(r+ROW_OFFSET, 4, fml % 'E', fmt_p, price_buyer[r])
        else:
            # Let values be entered by users, initially set at 0
            sheet.write(r+ROW_OFFSET, 1, 0, fmt_p)
            sheet.write(r+ROW_OFFSET, 2, 0, fmt_p)
            sheet.write(r+ROW_OFFSET, 3, 0, fmt_p)
            fml = "=F%(r)s-B%(r)s-C%(r)s-D%(r)s" % {'r': r+ROW_OFFSET+1}
            sheet.write(r+ROW_OFFSET, 4, fml, fmt_p, price_buyer[r])

    if extra_line:
        fml = "=SUMPRODUCT(" \
              "%(firstcol)s$%(u_price_row)s:%(lastcol)s$%(u_price_row)s," \
              "%(firstcol)s%(qty_row)s:%(lastcol)s%(qty_row)s)" % \
              {'firstcol': _col_name(COL_OFFSET),
               'lastcol': _col_name(n_products+COL_OFFSET-1),
               'u_price_row': 4,  # unit price
               'qty_row': n_buyers+ROW_OFFSET+1}
        fmt_p = fmt['hdr_user_price_cycle']
        sheet.write(n_buyers + ROW_OFFSET, COL_OFFSET-1, fml, fmt_p, 0)
        sheet.write(n_buyers + ROW_OFFSET, 1, 0, fmt_p)
        sheet.write(n_buyers + ROW_OFFSET, 2, 0, fmt_p)
        sheet.write(n_buyers + ROW_OFFSET, 3, 0, fmt_p)
        fml = "=F%(r)s-B%(r)s-C%(r)s-D%(r)s" % {'r': n_buyers+ROW_OFFSET+1}
        sheet.write(n_buyers + ROW_OFFSET, 4, fml, fmt_p, 0)

    # Total price for all users
    fml = "=SUM(%%(sumcol)s%(firstrow)s:%%(sumcol)s%(lastrow)s)" % \
          {'sumcol': _col_name(COL_OFFSET-1), 'firstrow':ROW_OFFSET+1, 'lastrow': n_buyers+ROW_OFFSET+extra_line}
    sheet.write(11, 1, fml % {'sumcol': 'B'}, fmt['hdr_price'], 0)
    sheet.write(11, 2, fml % {'sumcol': 'C'}, fmt['hdr_price'], 0)
    sheet.write(11, 3, fml % {'sumcol': 'D'}, fmt['hdr_price'], 0)
    sheet.write(11, 4, fml % {'sumcol': 'E'}, fmt['hdr_price'], 0)
    sheet.write(11, 5, fml % {'sumcol': 'F'}, fmt['hdr_price'], sum(price_buyer))


    # Total quantities and weights per product
    total_packages = 0
    for c, pd in enumerate(products):
        vars = {'colname': _col_name(c+COL_OFFSET), 'firstrow':ROW_OFFSET+1, 'lastrow': n_buyers+ROW_OFFSET+extra_line}
        qty = qty_product[c]

        # Quantity
        fml = "=SUM(%(colname)s%(firstrow)s:%(colname)s%(lastrow)s)" % vars
        sheet.write(6, c+COL_OFFSET, fml, fmt['hdr_qty'], qty)

        # Lose and packaged units
        if pd.quantity_per_package:
            (full, loose) = (qty // pd.quantity_per_package, qty % pd.quantity_per_package)
            total_packages += full
        else:
            (full, loose) = ("-", "-")
        fml = "=IF(ISNUMBER(%(colname)s6), TRUNC(%(colname)s7 / %(colname)s6), \"-\")" % vars
        sheet.write(7, c+COL_OFFSET, fml, fmt['hdr_qty'], full)
        fml = "=IF(ISNUMBER(%(colname)s6), MOD(%(colname)s7, %(colname)s6), \"-\")" % vars
        sheet.write(8, c+COL_OFFSET, fml, fmt['hdr_qty'], loose)

        # Weight
        fml = "=IF(ISNUMBER(%(colname)s5), %(colname)s7*%(colname)s5, \"?\")" % vars
        if pd.unit_weight:
            weight = pd.unit_weight * qty
        else:
            weight = "?"
        sheet.write(9, c+COL_OFFSET, fml, fmt['hdr_weight'], weight)
        sheet.write_blank(10, c+COL_OFFSET, None, fmt['hdr_blank'])

    # Total # of packages and weight
    vars = {'firstcol': _col_name(COL_OFFSET), 'lastcol': _col_name(n_products+COL_OFFSET-1)}
    fml = "=SUM(%(firstcol)s8:%(lastcol)s8)" % vars
    sheet.write(7, COL_OFFSET-1, fml, fmt['hdr_qty'], total_packages)
    fml = "=SUM(%(firstcol)s10:%(lastcol)s10)" % vars
    sheet.write(9, COL_OFFSET-1, fml, fmt['hdr_weight'], sum(weight_product))


def spreadsheet(delivery, subgroups):
    string_buffer = StringIO()  # Generate in a string rather than a file
    book = xls.Workbook(string_buffer, {'in_memory': True})
    def _red(n):
        return "#"+''.join(('%02x'%(255-(255-x)/n) for x in (0x81, 0x13, 0x05)))
    red1, red2, red3, red4 = _red(1), _red(2), _red(3), _red(10)
    fmt = {
        'hdr_title': book.add_format({'bold': True, 'bg_color': red2, 'font_color': 'white', 'align': 'center'}),
        'hdr_title_right': book.add_format({'bold': True, 'bg_color': red2, 'font_color': 'white', 'align': 'right'}),
        'hdr_price': book.add_format({'num_format': u'0.00€', 'bold': True, 'bg_color': red3}),
        'hdr_user_price': book.add_format({'num_format': u'0.00€', 'bold': True}),
        'hdr_user_price_cycle': book.add_format({'num_format': u'0.00€', 'bold': True, 'bg_color': red4}),
        'hdr_weight': book.add_format({'num_format': u'0.###"kg"', 'bold': True, 'bg_color': red3, 'align': 'right'}),
        'hdr_qty': book.add_format({'bold': True, 'bg_color': red3, 'align': 'right'}),
        'hdr_user_qty': book.add_format({'bold': True, 'bg_color': red3}),
        'hdr_user_qty_cycle': book.add_format({'bold': True, 'bg_color': red3}),
        'hdr_blank': book.add_format({'bg_color': red3}),

        'title': book.add_format({'bold': True, 'align': 'vjustify', 'font_color': red1, 'font_size': 24}),
        'price': book.add_format({'num_format': u'0.00€'}),
        'price_h_cycle': book.add_format({'num_format': u'0.00€', 'bg_color': red4}),
        'weight': book.add_format({'num_format': u'0.###"kg"'}),
        'qty': book.add_format({}),
        'qty_v_cycle': book.add_format({'bg_color': red4}),
        'qty_h_cycle': book.add_format({'bg_color': red4}),
        'qty_vh_cycle': book.add_format({}),
        'f_qty': book.add_format({}),
        'f_qty_v_cycle': book.add_format({'bg_color': red4}),
        'f_qty_h_cycle': book.add_format({'bg_color': red4}),
        'f_qty_vh_cycle': book.add_format({}),

        'user_name': book.add_format({'bold': True, 'font_color': red1, 'bg_color': red3, 'align': 'right'}),
        'user_name_cycle': book.add_format({'bold': True, 'font_color': red1, 'bg_color': red2, 'align': 'right'}),
        'pd_name': book.add_format({'font_size': 10, 'bg_color': red2, 'font_color': 'white', 'align': 'center', 'valign': 'bottom', 'text_wrap': True}),
    }
    # Everything but raw quantities is protected, i.e. everything with a style other than "qty_*"
    if PROTECT_FORMULA_CELLS:
        for name, f in fmt.iteritems():
            if name[0:2] == 'qty':
                f.set_locked(False)

    x = delivery_description(delivery, subgroups)

    one_group = len(subgroups) == 1
    if not one_group:
        buyers = [sg['subgroup'].name for sg in x['table']]
        def purchases(sg_idx, pd_idx):
            return x['table'][sg_idx]['totals'][pd_idx]['quantity']
        def purchase_fmls(sg_idx, pd_idx):
            return "=%(subgroup)s!%(colname)s$7" % {
                'subgroup':x['table'][sg_idx]['subgroup'].name,
                'colname':_col_name(pd_idx+COL_OFFSET)}

        _make_sheet(book, "Commande", fmt, buyers, x['products'], purchases, purchase_fmls,
                    group_recap=True, extra_line=1, extra_fmls=None)

        if delivery.state >= delivery.REGULATING:

            # 1 - Add discrepancies sheet
            def purchases(sg_idx, pd_idx):
                return x['table'][sg_idx]['totals'][pd_idx]['discrepancy']
            _make_sheet(book, "Ecarts", fmt, buyers, x['products'], purchases, group_recap=False,
                        one_group=one_group, extra_line=1)

            # 2 - Add final count sheet
            def purchases(sg_idx, pd_idx):
                t = x['table'][sg_idx]['totals'][pd_idx]
                return t['quantity'] + t['discrepancy']
            def purchase_fmls(sg_idx, pd_idx):
                return "=Commande!%(colname)s%(rowname)s+Ecarts!%(colname)s%(rowname)s" % {
                    'rowname': sg_idx + ROW_OFFSET + 1,
                    'colname': _col_name(pd_idx+COL_OFFSET)}
            _make_sheet(book, "Livraison", fmt, buyers, x['products'], purchases, purchase_fmls,
                        group_recap=False, one_group=one_group, extra_line=1, extra_fmls=purchase_fmls)

    # subgroups
    for sg in x['table']:
        title = _u8(sg['subgroup'].name)
        buyers = [u['user'].first_name + " " + u['user'].last_name for u in sg['users']]
        def purchases(u_idx, pd_idx):
            return sg['users'][u_idx]['orders'].purchases[pd_idx].quantity
        _make_sheet(book, title, fmt, buyers, x['products'], purchases, group_recap=False,
                    one_group=one_group, extra_line=one_group)



    book.close()
    return string_buffer.getvalue()
