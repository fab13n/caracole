#!/usr/bin/python
# -*- coding: utf8 -*-

"""Excel spreadsheet views generator."""

from .delivery_table_view import delivery_description


def _u8(s):
    return str(s).decode('utf-8')


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
    header_fmt = book.add_format({'bold': True, 'bg_color': 'gray'})
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
        sheet = book.add_worksheet("Totaux par groupes")
        sheet.write(n_subgroups+1, 0, 'Total', header_fmt)

        # Horizontal header (product names)
        for c, pd in enumerate(x['products']):
            sheet.write(0, c+1, pd.name.decode('utf-8'), header_fmt)

        # Vertical header (subgroup names)
        for r, s in enumerate(x['table']):
            sheet.write(r+1, 0, s['subgroup'].name.decode('utf-8'), header_fmt)

        # Totals per product and subgroup (2D matrix)
        for r, s in enumerate(x['table']):
            for c, p in enumerate(s['totals']):
                sheet.write(r+1, c+1, p['quantity'], qty_fmt)

        # Computed sum per product for all subg-groups (last row)
        for c, p in enumerate(x['product_totals']):
            fml = "=SUM(%(colname)s2:%(colname)s%(lastrow)s)" % {'colname': col_name(c+1), 'lastrow': n_subgroups+1}
            sheet.write(n_subgroups+1, c+1, fml, sum_fmt, p['quantity'])

        sheet_title = "Commandes individuelles"
    else:
        sheet_title = "Commandes %s %s" % (delivery.network.name, subgroups[0].name.decode('utf-8'))

    # Index of the first line with user purchases, allows to move the table's vertical position
    # within the sheet.
    HEADER_HEIGHT = 4

    # Fixed Cells
    sheet = book.add_worksheet(sheet_title)
    sheet.write(0, 0, "Livraison:")
    sheet.write(0, 1, x['delivery'].name, title_fmt)
    sheet.write(0, 2, "Sous-groupe:")
    if n_subgroups == 1:
        sheet.write(0, 3, subgroups[0].name.decode('utf-8'), title_fmt)
    sheet.write(HEADER_HEIGHT-2, 0, "Produit", title_fmt)
    sheet.write(HEADER_HEIGHT-1, 0, "Prix unitaire", title_fmt)
    sheet.write(HEADER_HEIGHT-2, n_products+1, "total", title_fmt)

    # Generate product names and prices rows
    for c, pd in enumerate(x['products']):
        sheet.write(HEADER_HEIGHT-2, c+1, pd.name.decode('utf-8'), header_fmt)
        sheet.write(HEADER_HEIGHT-1, c+1, pd.price, price_fmt)

    users = [z for y in x['table'] for z in y['users']]
    n_users = len(users)

    # Generate username columns. Rows 1,2 are taken by headers
    for r, u in enumerate(users):
        sheet.write(r+HEADER_HEIGHT, 0, (u['user'].first_name+' '+u['user'].last_name).decode('utf-8'), header_fmt)

    # Fill user commands
    for c, pd in enumerate(x['products']):
        for r, u in enumerate(users):
            order = u['orders'].purchases[c]
            quantity = order.granted if order else 0
            sheet.write(r+HEADER_HEIGHT, c+1, quantity)

    # Total price per user, for every user in every subgroup
    for y in x['table']:
        for r, u in enumerate(y['users']):
            fml = "=SUMPRODUCT(B%(firstrow)s:%(lastcol)s%(firstrow)s,B%(lastrow)s:%(lastcol)s%(lastrow)s)" % \
                  {'firstrow': HEADER_HEIGHT, 'lastcol':col_name(n_products), 'lastrow': r+HEADER_HEIGHT+1}
            sheet.write(r+HEADER_HEIGHT, n_products+1, fml, price_sum_fmt, u['price'])

    # Total quantity per product
    for c, pd in enumerate(x['products']):
        fml = "=SUM(%(colname)s%(firstrow)s:%(colname)s%(lastrow)s)" % \
              {'colname': col_name(c+1), 'firstrow':HEADER_HEIGHT+1, 'lastrow': n_users+HEADER_HEIGHT}
        val = x['product_totals'][c]['quantity']
        sheet.write(n_users+HEADER_HEIGHT, c+1, fml, sum_fmt, val)

    # Grand total
    fml = "=SUM(%(sumcol)s%(firstrow)s:%(sumcol)s%(lastrow)s)" % \
          {'sumcol': col_name(n_products+1),'firstrow':HEADER_HEIGHT+1, 'lastrow':n_users+HEADER_HEIGHT}
    val = x['price']
    sheet.write(n_users+HEADER_HEIGHT, n_products+1, fml, price_sum_fmt, val)

    book.close()
    return string_buffer.getvalue()
