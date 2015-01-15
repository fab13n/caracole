#!/usr/bin/python
# -*- coding: utf8 -*-

"""Excel spreadsheet views generator."""

from StringIO import StringIO
import xlsxwriter as xls

from .delivery_description import delivery_description

DATABASE_UTF8_ENABLED = True


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
ROW_OFFSET = 11
COL_OFFSET = 2


def _make_sheet(book, title, fmt, buyers, products, purchases):
    """
    :param buyers: ordered list of buyers
    :param products: ordered list of products
    :param purchases: function (buyer_idx, product_idx) -> quantity
    :return:
    """

    # Fixed Cells
    sheet = book.add_worksheet(title)
    sheet.set_column(0, 0, 30)
    sheet.set_row(2, 50)
    sheet.write(0, 0, u"Achats:")
    sheet.write(0, 1, _u8(title), fmt['title'])
    sheet.write(2, 0, u"Produit", fmt['title'])
    sheet.write(3, 0, u"Prix unitaire", fmt['title'])
    sheet.write(4, 0, u"Poids unitaire", fmt['title'])
    sheet.write(5, 0, u"Nombre par carton", fmt['title'])
    sheet.write(6, 0, u"Nombre de pièces", fmt['title'])
    sheet.write(7, 0, u"Nombre de cartons", fmt['title'])
    sheet.write(8, 0, u"Nombre en complément", fmt['title'])
    sheet.write(9, 0, u"Poids total", fmt['title'])
    sheet.write(2, 1, u"Prix/Totaux", fmt['title'])

    # Generate product names and prices rows
    for c, pd in enumerate(products):
        sheet.write(2, c+COL_OFFSET, _u8(pd.name), fmt['pd_name'])  # 2/3: Name
        sheet.write(3, c+COL_OFFSET, pd.price, fmt['price'])        # 3/4: Unit price
        sheet.write(4, c+COL_OFFSET, pd.unit_weight, fmt['weight']) # 4/5: Unit weight
        sheet.write(5, c+COL_OFFSET, pd.quantity_per_package)    # 5/6: per package
                                                                 # 6/7: # units
                                                                 # 7/8: # full ackages
                                                                 # 8/9: # lose units
                                                                 # 9/10: total weight
                                                                 # 10/11: total price (1 cell)
    n_products = len(products)
    n_buyers = len(buyers)
    price_buyer = [0 for _ in buyers]
    weight_buyer = [0 for _ in buyers]
    qty_buyer = [0 for _ in buyers]
    qty_product = [0 for _ in products]
    weight_product = [0 for _ in products]

    # Generate buyer name columns.
    for r, name in enumerate(buyers):
        sheet.write(r+ROW_OFFSET, 0, _u8(name), fmt['user_name'])

    # Fill purchases, count totals
    for c, pd in enumerate(products):
        for r in range(n_buyers):
            qty = purchases(r, c)
            sheet.write(r+ROW_OFFSET, c+COL_OFFSET, qty)
            qty_buyer[r] += qty
            qty_product[c] += qty
            price_buyer[r] += qty * pd.price
            if pd.unit_weight:
                w = qty * pd.unit_weight
                weight_buyer[r] += w
                weight_product[c] += w

    # Total price per buyer
    for r in range(n_buyers):
        fml = "=SUMPRODUCT(" \
              "%(firstcol)s$%(firstrow)s:%(lastcol)s$%(firstrow)s," \
              "%(firstcol)s%(lastrow)s:%(lastcol)s%(lastrow)s)" % \
              {'firstcol': _col_name(COL_OFFSET),
               'lastcol': _col_name(n_products+COL_OFFSET-1),
               'firstrow': 4,  # unit price
               'lastrow': r+ROW_OFFSET+1}
        sheet.write(r+ROW_OFFSET, 1, fml, fmt['price_sum'], price_buyer[r])

    # Total price for all users
    fml = "=SUM($%(sumcol)s%(firstrow)s:$%(sumcol)s%(lastrow)s)" % \
          {'sumcol': _col_name(1), 'firstrow':ROW_OFFSET+1, 'lastrow':n_buyers+ROW_OFFSET}
    sheet.write(10, 0, "Prix total", fmt['title'])
    sheet.write(10, 1, fml, fmt['price_sum'], sum(price_buyer))

    total_packages = 0

    # Total quantity per product
    for c, pd in enumerate(products):
        vars = {'colname': _col_name(c+COL_OFFSET), 'firstrow':ROW_OFFSET+1, 'lastrow': n_buyers+ROW_OFFSET}
        qty = qty_product[c]

        # Quantity
        fml = "=SUM(%(colname)s%(firstrow)s:%(colname)s%(lastrow)s)" % vars
        sheet.write(6, c+COL_OFFSET, fml, fmt['sum'], qty)

        # Lose and packaged units
        if pd.quantity_per_package:
            (full, loose) = (qty // pd.quantity_per_package, qty % pd.quantity_per_package)
            total_packages += full
        else:
            (full, loose) = ("-", "-")
        fml = "=IF(%(colname)s6>0, TRUNC(%(colname)s7 / %(colname)s6), \"-\")" % vars
        sheet.write(7, c+COL_OFFSET, fml, fmt['qty'], full)
        fml = "=IF(%(colname)s6>0, MOD(%(colname)s7, %(colname)s6), \"-\")" % vars
        sheet.write(8, c+COL_OFFSET, fml, fmt['qty'], loose)

        # Weight
        fml = "=IF(ISNUMBER(%(colname)s5), %(colname)s7*%(colname)s5, \"?\")" % vars
        if pd.unit_weight:
            weight = pd.unit_weight * qty
        else:
            weight = "?"
        sheet.write(9, c+COL_OFFSET, fml, fmt['weight'], weight)

    # Total # of packages and weight
    vars = {'firstcol': _col_name(COL_OFFSET), 'lastcol': _col_name(n_products+COL_OFFSET-1)}
    fml = "=SUM(%(firstcol)s8:%(lastcol)s8)" % vars
    sheet.write(7, 1, fml, fmt['qty'], total_packages)
    fml = "=SUM(%(firstcol)s10:%(lastcol)s10)" % vars
    sheet.write(9, 1, fml, fmt['weight'], sum(weight_product))


def spreadsheet(delivery, subgroups):
    string_buffer = StringIO()  # Generate in a string rather than a file
    book = xls.Workbook(string_buffer, {'in_memory': True})
    fmt = {
        'price': book.add_format({'num_format': u'#,##0.00€'}),
        'price_sum': book.add_format({'num_format': u'#,##0.00€', 'bold': True}),
        'weight': book.add_format({'num_format': u'0"kg"'}),
        'user_name': book.add_format({'bold': True, 'bg_color': 'gray'}),
        'pd_name': book.add_format({'bold': True, 'bg_color': 'gray', 'align': 'vjustify'}),
        'sum': book.add_format({'bold': True}),
        'title': book.add_format({'bold': True}),
        'qty': book.add_format({})}

    x = delivery_description(delivery, subgroups)
    title = "XXXXX"
    buyers = [u['user'].first_name+' '+u['user'].last_name for sg in x['table'] for u in sg['users']]
    u2sg_idx = [(u_idx, sg_idx) for sg_idx, sg in enumerate(x['table']) for (u_idx, _) in enumerate(sg['users'])]

    def purchases(u_idx, pd_idx):
        u_sg_idx, sg_idx = u2sg_idx[u_idx]
        print "purchase(%d, %d):" % (u_idx, pd_idx)
        print x['table'][sg_idx]['users'][u_sg_idx]['orders'].purchases[pd_idx].granted
        return x['table'][sg_idx]['users'][u_sg_idx]['orders'].purchases[pd_idx].granted

    _make_sheet(book, title, fmt, buyers, x['products'], purchases)

    book.close()
    return string_buffer.getvalue()
