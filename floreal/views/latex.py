#!/usr/bin/env python3
# -*-coding: utf-8 -*-
import os
import subprocess
from tempfile import NamedTemporaryFile

from django.template.loader import get_template
from .delivery_description import delivery_description

LATEX_RUN_TIMEOUT = 30  # seconds
RERUN_LATEX_IF = [
    b"Package longtable Warning: Table widths have changed. Rerun LaTeX."
]
def render_latex(template_name, ctx):
        
    t = get_template(template_name)
    tex_unicode = t.render(ctx)
    tex_string = tex_unicode.encode('utf8')
    with NamedTemporaryFile(suffix='.tex', delete=False) as f:
        f.write(tex_string)
        f.flush()
        src_file_name = f.name
        dst_file_name = os.path.splitext(src_file_name)[0]+".pdf"
        # print("Generated tex file %s" % src_file_name)
        prev_dir = os.getcwd()
        try:
            os.chdir("/tmp/")
            cmd = ["pdflatex", "-halt-on-error", src_file_name]
            # Run Latex up to 3 times, as longtable may need multiple runs to 
            for i in range(3):
                try:
                    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
                    output, errors = p.communicate(timeout=LATEX_RUN_TIMEOUT)
                    assert p.returncode == 0, "Impossible de compiler "+src_file_name

                    if any(line in output for line in RERUN_LATEX_IF):
                        print("RUN AGAIN")
                        pass
                    else:
                        # print(output.decode('utf8'))
                        break
                except subprocess.TimeoutExpired: 
                    # Avoid resource leaks upon timeout
                    p.kill()
                    output, errors = p.communicate()

            with open(dst_file_name, "rb") as g:
                pdf_string = g.read()
        finally:
            os.chdir(prev_dir)
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