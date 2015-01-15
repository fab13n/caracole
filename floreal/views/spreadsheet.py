#!/usr/bin/python
# -*- coding: utf8 -*-

"""Excel spreadsheet views generator."""

from .delivery_description import delivery_description

DATABASE_UTF8_ENABLED = True

def _u8(s):
    """Convert DB contents into UTF8 if necessary."""
    return unicode(s) if DATABASE_UTF8_ENABLED else str(s).decode('utf-8')


def spreadsheet(delivery, subgroups):
    from StringIO import StringIO
    import xlsxwriter as xls
    string_buffer = StringIO()  # Generate in a string rather than a file
    x = delivery_description(delivery, subgroups)
    n_products = len(x['products'])
    n_subgroups = len(subgroups)

    book = xls.Workbook(string_buffer, {'in_memory': True})

    price_fmt = book.add_format({'num_format': u'#,##0.00€'})
    price_sum_fmt = book.add_format({'num_format': u'#,##0.00€', 'bold': True})
    weight_fmt = book.add_format({'num_format': u'0"kg"'})
    user_name_fmt = book.add_format({'bold': True, 'bg_color': 'gray'})
    pd_name_fmt = book.add_format({'bold': True, 'bg_color': 'gray', 'align': 'vjustify'})
    sum_fmt = book.add_format({'bold': True})
    title_fmt = book.add_format({'bold': True})
    qty_fmt = book.add_format({})

    # Convert a zero-based index into an Excel column name
    def col_name(c):
        if c < 26:
            return chr(65+c)
        elif c < 26*27:
            return chr(64+c/26) + chr(65+c%26)
        else:
            raise Exception("Too many products")

    # If there's more than one subgroup, make a per-subgroup sum-up
    # as the first spreadsheet sheet.
    # User purchases will be collected ina second sheet.
    if n_subgroups > 1:
        sheet = book.add_worksheet(u"Totaux par groupes")
        sheet.write(n_subgroups+1, 0, 'Total', title_fmt)

        # Horizontal header (product names)
        for c, pd in enumerate(x['products']):
            sheet.write(0, c+1, _u8(pd.name), title_fmt)

        # Vertical header (subgroup names)
        for r, s in enumerate(x['table']):
            sheet.write(r+1, 0, _u8(s['subgroup'].name), title_fmt)

        # Totals per product and subgroup (2D matrix)
        for r, s in enumerate(x['table']):
            for c, p in enumerate(s['totals']):
                sheet.write(r+1, c+1, p['quantity'], qty_fmt)

        # Computed sum per product for all subg-groups (last row)
        for c, p in enumerate(x['product_totals']):
            fml = "=SUM(%(colname)s2:%(colname)s%(lastrow)s)" % {'colname': col_name(c+1), 'lastrow': n_subgroups+1}
            sheet.write(n_subgroups+1, c+1, fml, sum_fmt, p['quantity'])

        sheet_title = u"Commandes individuelles"
    else:
        sheet_title = u"Commandes %s %s" % (_u8(delivery.network.name), _u8(subgroups[0].name))


    # By how much the first element of the 2D user/product quantity matrix is shifted
    ROW_OFFSET = 11
    COL_OFFSET = 2

    # Fixed Cells
    sheet = book.add_worksheet(sheet_title)
    sheet.set_column(0, 0, 30)
    sheet.set_row(2, 50)
    sheet.write(0, 0, u"Livraison:")
    sheet.write(0, 1, _u8(x['delivery'].name), title_fmt)
    sheet.write(0, 2, u"Sous-groupe:")
    if n_subgroups == 1:
        sheet.write(0, 3, _u8(subgroups[0].name), title_fmt)
    sheet.write(2, 0, u"Produit", title_fmt)
    sheet.write(3, 0, u"Prix unitaire", title_fmt)
    sheet.write(4, 0, u"Poids unitaire", title_fmt)
    sheet.write(5, 0, u"Nombre par carton", title_fmt)
    sheet.write(6, 0, u"Nombre de pièces", title_fmt)
    sheet.write(7, 0, u"Nombre de cartons", title_fmt)
    sheet.write(8, 0, u"Nombre en complément", title_fmt)
    sheet.write(9, 0, u"Poids total", title_fmt)
    sheet.write(2, 1, u"Prix/Totaux", title_fmt)

    # Generate product names and prices rows
    for c, pd in enumerate(x['products']):
        sheet.write(2, c+COL_OFFSET, _u8(pd.name), pd_name_fmt)  # 2/3: Name
        sheet.write(3, c+COL_OFFSET, pd.price, price_fmt)        # 3/4: Unit price
        sheet.write(4, c+COL_OFFSET, pd.unit_weight, weight_fmt) # 4/5: Unit weight
        sheet.write(5, c+COL_OFFSET, pd.quantity_per_package)    # 5/6: per package
                                                                 # 6/7: # units
                                                                 # 7/8: # full ackages
                                                                 # 8/9: # lose units
                                                                 # 9/10: total weight
                                                                 # 10/11: total price (1 cell)

    users = [u for sg in x['table'] for u in sg['users']]
    n_users = len(users)
    print "users"
    print [u['user'] for u in users]

    # Generate username columns. Rows 1,2 are taken by headers
    for r, u in enumerate(users):
        sheet.write(r+ROW_OFFSET, 0, _u8(u['user'].first_name+' '+u['user'].last_name), user_name_fmt)

    # Fill user commands
    for c, pd in enumerate(x['products']):
        for r, u in enumerate(users):
            order = u['orders'].purchases[c]
            quantity = order.granted if order else 0
            sheet.write(r+ROW_OFFSET, c+COL_OFFSET, quantity)

    # Total price per user, for every user in every subgroup
    r = 0
    for sg in x['table']:
        for u in sg['users']:
            fml = "=SUMPRODUCT(" \
                  "%(firstcol)s$%(firstrow)s:%(lastcol)s$%(firstrow)s," \
                  "%(firstcol)s%(lastrow)s:%(lastcol)s%(lastrow)s)" % \
                  {'firstcol': col_name(COL_OFFSET),
                   'lastcol': col_name(n_products+COL_OFFSET-1),
                   'firstrow': 4,  # unit price
                   'lastrow': r+ROW_OFFSET+1}
            sheet.write(r+ROW_OFFSET, 1, fml, price_sum_fmt, u['price'])
            r += 1

    # Total price for all users
    fml = "=SUM($%(sumcol)s%(firstrow)s:$%(sumcol)s%(lastrow)s)" % \
          {'sumcol': col_name(1), 'firstrow':ROW_OFFSET+1, 'lastrow':n_users+ROW_OFFSET}
    val = x['price']
    sheet.write(10, 0, "Prix total", title_fmt)
    sheet.write(10, 1, fml, price_sum_fmt, val)


    total_weight = 0
    total_packages = 0

    # Total quantity per product
    for c, pd in enumerate(x['products']):
        vars = {'colname': col_name(c+COL_OFFSET), 'firstrow':ROW_OFFSET+1, 'lastrow': n_users+ROW_OFFSET}
        qty = x['product_totals'][c]['quantity']

        # Quantity
        fml = "=SUM(%(colname)s%(firstrow)s:%(colname)s%(lastrow)s)" % vars
        sheet.write(6, c+COL_OFFSET, fml, sum_fmt, qty)

        # Lose and packaged units
        if pd.quantity_per_package:
            (full, loose) = (qty // pd.quantity_per_package, qty % pd.quantity_per_package)
            total_packages += full
        else:
            (full, loose) = ("-", "-")
        fml = "=IF(%(colname)s6>0, TRUNC(%(colname)s7 / %(colname)s6), \"-\")" % vars
        sheet.write(7, c+COL_OFFSET, fml, qty_fmt, full)
        fml = "=IF(%(colname)s6>0, MOD(%(colname)s7, %(colname)s6), \"-\")" % vars
        sheet.write(8, c+COL_OFFSET, fml, qty_fmt, loose)

        # Weight
        fml = "=IF(ISNUMBER(%(colname)s5), %(colname)s7*%(colname)s5, \"?\")" % vars
        if pd.unit_weight:
            weight = pd.unit_weight * qty
            total_weight += weight
        else:
            weight = "?"
        sheet.write(9, c+COL_OFFSET, fml, weight_fmt, weight)

    # Total # of packages and weight
    vars = {'firstcol': col_name(COL_OFFSET), 'lastcol': col_name(n_products+COL_OFFSET-1)}
    fml = "=SUM(%(firstcol)s8:%(lastcol)s8)" % vars
    sheet.write(7, 1, fml, qty_fmt, total_packages)
    fml = "=SUM(%(firstcol)s10:%(lastcol)s10)" % vars
    sheet.write(9, 1, fml, weight_fmt, total_weight)

    book.close()
    return string_buffer.getvalue()
