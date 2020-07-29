#!/usr/bin/python3
# -*- coding: utf8 -*-

"""Excel spreadsheet views generator."""

from io import BytesIO
import xlsxwriter as xls


from floreal.views.dd2 import DeliveryDescription, NetworkDeliveryDescription

DATABASE_UTF8_ENABLED = True
PROTECT_FORMULA_CELLS = False


def _u8(s):
    """Convert DB contents into UTF8 if necessary."""
    return str(s) if DATABASE_UTF8_ENABLED else str(s).decode('utf-8')


def _col_name(c):
    """Convert a zero-based index into an Excel column name."""
    if c < 26:
        return chr(65+c)
    elif c < 26*27:
        return chr(64+c//26) + chr(65+c%26)
    else: # more than 701 products, seriously?!
        raise Exception("Too many products")

# By how much the first element of the 2D user/product quantity matrix is shifted
ROW_OFFSET = 11
COL_OFFSET =  2

V_CYCLE_LENGTH = 5
H_CYCLE_LENGTH = 5

def _make_sheet(book, title, fmt, buyers, products, purchases, purchase_fmls, recopy_products):
    """
    Insert one sheet of (buyer, product) -> purchase matrix in an Excel book,
    with custom purchase values and formulae (Excel needs both). Optionally,
    an extra user line can be handled too.

    :param book: where the sheet will be added
    :param title: name of the sheet
    :param fmt: dictionary of Excel formats
    :param buyers: ordered list of buyers
    :param products: ordered list of products
    :param purchases: function (buyer_idx, product_idx) -> quantity
    :param purchase_fmls: Optional (user_index, pd_index) -> formula function
    """
    if len(title) > 31:
        # Excel sheet names can't be longer than 31 chars
        title = title[:28] + "..."
    sheet = book.add_worksheet(title)
    if PROTECT_FORMULA_CELLS:
        sheet.protect()
    sheet.set_column(0, 0, 30)
    sheet.set_column(1, 1, 12)
    sheet.set_row(0, 75)
    sheet.set_row(2, 50)
    sheet.merge_range('A1:J1', products[0].delivery.name, fmt['title'])
    sheet.freeze_panes(ROW_OFFSET, COL_OFFSET)
    for row, title in enumerate(["Prix unitaire", "Poids unitaire", "Nombre par carton",
                                 "Nombre de pièces", "Nombre de cartons", "Nombre en complément",
                                 "Poids total"]):
        sheet.write('A%d'%(row+4), title, fmt['hdr_title_right'])
    for r in range(3, 12):
        sheet.write_blank(r, COL_OFFSET-1, None, fmt['hdr_blank'])
    sheet.write(2, COL_OFFSET-1, "Prix\n&\nTotaux", fmt['hdr_title'])

    # Generate product names and prices rows on the first (possibly only) sheet
    if not recopy_products:
        # Product descriptions are written directly here, not taken from mainpage
        for c, pd in enumerate(products):
            # python row / Excel row: content
            # 2/3: Name
            # 3/4: Unit price
            # 4/5: Unit weight
            # 5/6: per package
            # 6/7: number of units
            # 7/8: number of packages
            # 8/9: number loose units
            # 9/10: total weight
            # 10/11: total price (1 cell)
            sheet.write(2, c+COL_OFFSET, _u8(pd.name), fmt['pd_name'])
            sheet.write(3, c+COL_OFFSET, pd.price, fmt['hdr_price'])
            sheet.write(4, c+COL_OFFSET, pd.unit_weight, fmt['hdr_weight'])
            sheet.write(5, c+COL_OFFSET, pd.quantity_per_package or "-", fmt['hdr_qty'])
    else:
        # In subgroup sheets, recopy product descriptions formulaicly from 1st page
        for c, pd in enumerate(products):
            fml = "=Commande!%(col)s%%s" % {'col': _col_name(c+COL_OFFSET)}
            sheet.write(2, c+COL_OFFSET, fml % 3, fmt['pd_name'], _u8(pd.name))
            sheet.write(3, c+COL_OFFSET, fml % 4, fmt['hdr_price'], pd.price)
            sheet.write(4, c+COL_OFFSET, fml % 5, fmt['hdr_weight'], pd.unit_weight)
            sheet.write(5, c+COL_OFFSET, fml % 6, fmt['hdr_qty'], pd.quantity_per_package)

    n_products = len(products)
    n_buyers = len(buyers)
    price_buyer = [0] * n_buyers
    weight_buyer = [0] * n_buyers
    qty_buyer = [0] * n_buyers
    qty_product = [0] * n_products
    weight_product = [0] * n_products

    # Generate buyer names column.
    for r, name in enumerate(buyers):
        fmt_u = fmt['user_name_cycle'] if r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1 else fmt['user_name']
        sheet.write(r+ROW_OFFSET, 0, _u8(name), fmt_u)

    # Fill purchases, count totals
    for c, pd in enumerate(products):
        h_cycle = c % H_CYCLE_LENGTH == H_CYCLE_LENGTH - 1
        for r in range(n_buyers):
            qty = purchases(r, c)
            v_cycle = r % V_CYCLE_LENGTH == V_CYCLE_LENGTH-1
            if h_cycle and v_cycle:  fmt_name = 'qty_vh_cycle'
            elif h_cycle:            fmt_name = 'qty_h_cycle'
            elif v_cycle:            fmt_name = 'qty_v_cycle'
            else:                    fmt_name = 'qty'

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

    # Total price per buyer
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

    # TODO conditional formatting, make zero values less conspicious (light gray, smaller font...)
    # TODO https://xlsxwriter.readthedocs.io/working_with_conditional_formats.html
    purchase_cells = f"{_col_name(COL_OFFSET)}{ROW_OFFSET+1}:{_col_name(COL_OFFSET+n_products-1)}{ROW_OFFSET+n_buyers}"
    sheet.conditional_format(purchase_cells, {
        'type': 'cell',
        'criteria': '==',
        'value': 0,
        'format': fmt['zero']
    })

    # Total price for all users
    fml = "=SUM(%%(sumcol)s%(firstrow)s:%%(sumcol)s%(lastrow)s)" % \
          {'sumcol': _col_name(COL_OFFSET-1), 'firstrow':ROW_OFFSET+1, 'lastrow': n_buyers+ROW_OFFSET}

    sheet.write(10, 0, "Prix total", fmt['hdr_title_right'])
    sheet.write(10, 1, fml % {'sumcol': 'B'}, fmt['hdr_price'], sum(price_buyer))

    # Total quantities and weights per product
    total_packages = 0
    for c, pd in enumerate(products):
        vars = {'colname': _col_name(c+COL_OFFSET), 'firstrow':ROW_OFFSET+1, 'lastrow': n_buyers+ROW_OFFSET}
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

        # Total price per product
        fml = "=%(colname)s4*%(colname)s7" % vars
        sheet.write(ROW_OFFSET-1, c+COL_OFFSET, fml, fmt['hdr_price'], pd.price*qty)

    # Total # of packages and weight
    vars = {'firstcol': _col_name(COL_OFFSET), 'lastcol': _col_name(n_products+COL_OFFSET-1)}
    fml = "=SUM(%(firstcol)s8:%(lastcol)s8)" % vars
    sheet.write(7, COL_OFFSET-1, fml, fmt['hdr_qty'], total_packages)
    fml = "=SUM(%(firstcol)s10:%(lastcol)s10)" % vars
    sheet.write(9, COL_OFFSET-1, fml, fmt['hdr_weight'], sum(weight_product))



def spreadsheet(delivery, network=None):
    bytes_buffer = BytesIO()  # Generate in a string rather than a file
    book = xls.Workbook(bytes_buffer, {'in_memory': True})
    def _red(n):
        return "#"+''.join(('%02x'%(255-(255-x)//n) for x in (0x81, 0x13, 0x05)))
    red1, red2, red3, red4 = _red(1), _red(2), _red(3), _red(10)
    fmt = {
        'hdr_title': book.add_format({'bold': True, 'bg_color': red2, 'font_color': 'white', 'align': 'center'}),
        'hdr_title_right': book.add_format({'bold': True, 'bg_color': red2, 'font_color': 'white', 'align': 'right'}),
        'hdr_price': book.add_format({'num_format': '0.00€', 'bold': True, 'bg_color': red3}),
        'hdr_user_price': book.add_format({'num_format': '0.00€', 'bold': True}),
        'hdr_user_price_cycle': book.add_format({'num_format': '0.00€', 'bold': True, 'bg_color': red4}),
        'hdr_weight': book.add_format({'num_format': '0.###"kg"', 'bold': True, 'bg_color': red3, 'align': 'right'}),
        'hdr_qty': book.add_format({'bold': True, 'bg_color': red3, 'align': 'right'}),
        'hdr_user_qty': book.add_format({'bold': True, 'bg_color': red3}),
        'hdr_user_qty_cycle': book.add_format({'bold': True, 'bg_color': red3}),
        'hdr_blank': book.add_format({'bg_color': red3}),

        'title': book.add_format({'bold': True, 'align': 'vjustify', 'font_color': red1, 'font_size': 24}),
        'price': book.add_format({'num_format': '0.00€'}),
        'price_h_cycle': book.add_format({'num_format': '0.00€', 'bg_color': red4}),
        'weight': book.add_format({'num_format': '0.###"kg"'}),
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

        'zero': book.add_format({'font_color': '#c0c0c0'}),
    }
    # Everything but raw quantities is protected, i.e. everything with a style other than "qty_*"
    if PROTECT_FORMULA_CELLS:
        for name, f in fmt.items():
            if name[0:2] == 'qty':
                f.set_locked(False)

    if network is not None:
        single_network = True
    elif len(networks := delivery.networks.all()) == 1:
        network = networks[0]
        single_network = True
    else:
        single_network = False

    if single_network:
        network_descriptions = [NetworkDeliveryDescription(delivery, network)]
    else:
        # There are several networks, they will have one page each, plus the recap
        dd = DeliveryDescription(delivery)
        network_descriptions = dd.network_descriptions

        buyers = [nwd.network.name for nwd in dd.network_descriptions]
        def purchases(nw_idx, pd_idx):
            pc = dd.columns[nw_idx].purchases[pd_ix]
            return pc.quantity if pc is not None else 0
            # return x['table'][sg_idx]['totals'][pd_idx]['quantity']
        def purchase_fmls(nw_idx, pd_idx):
            nw = dd.network_descriptions[nw_idx].network.name
            col = col_name(pd_idx + COL_OFFSET)
            return f"={nw}!{col}$7"
            # return "=%(subgroup)s!%(colname)s$7" % {
            #     'subgroup':x['table'][sg_idx]['subgroup'].name,
            #     'colname':_col_name(pd_idx+COL_OFFSET)}

        _make_sheet(book, "Commande", fmt, buyers, x['products'], purchases, purchase_fmls,
                    recopy_products=False)

    # Each network has its sheet
    for ndd in network_descriptions:
        title = _u8(ndd.network.name)
        buyers = [u.first_name + " " + u.last_name for u in ndd.users]
        def purchases(u_idx, pd_idx):
            pc = ndd.columns[pd_idx].purchases[u_idx]
            return pc.quantity if pc is not None else 0
        _make_sheet(book, title, fmt, buyers, ndd.products, 
                    purchases, purchase_fmls=None,
                    recopy_products=not single_network)

    book.close()
    return bytes_buffer.getvalue()
