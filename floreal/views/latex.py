#!/usr/bin/env python3
# -*-coding: utf-8 -*-
import os
from tempfile import NamedTemporaryFile

from django.template.loader import get_template

from .delivery_description import delivery_description


def render_latex(template_name, ctx):
    t = get_template(template_name)
    tex_unicode = t.render(ctx)
    tex_string = tex_unicode.encode('utf8')
    with NamedTemporaryFile(suffix='.tex', delete=False) as f:
        f.write(tex_string)
        f.flush()
        src_file_name = f.name
        dst_file_name = os.path.splitext(src_file_name)[0]+".pdf"
        print("Generated tex file %s" % src_file_name)
        os.chdir("/tmp/")
        # TODO: popen + grep to get the warning about tables to be re-run
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        with open(dst_file_name, "rb") as g:
            pdf_string = g.read()
    return pdf_string


def cards(dv, sg):
    descr = delivery_description(dv, [sg])
    # Maximum number of purchase lines in the delivery description
    # TODO: won't work with multiple subgroups (multiple elements in ['table'])
    descr['max_order_size'] = max(len([pc for pc in ur['orders'].purchases if pc]) for ur in descr['table'][0]['users'])
    return render_latex("subgroup-cards.tex", {'d': descr})


def subgroup(dv, sg):
    descr = delivery_description(dv, [sg])
    return render_latex("subgroup-table.tex", {'d': descr})


def delivery_cards(dv):
    descr = delivery_description(dv, dv.network.subgroup_set.all())
    return render_latex("delivery-cards.tex", {'d': descr})


def delivery_table(dv):
    descr = delivery_description(dv, dv.network.subgroup_set.all())
    return render_latex("delivery-table.tex", {'d': descr})

def emails(nw):
    return render_latex("emails.tex", {"nw": nw})