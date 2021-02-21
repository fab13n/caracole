#!/usr/bin/env python3
# -*-coding: utf-8 -*-
import os
import subprocess
from tempfile import NamedTemporaryFile

from django.template.loader import get_template
from .delivery_description import FlatDeliveryDescription


LATEX_RUN_TIMEOUT = 30  # seconds


RERUN_LATEX_IF = [
    b"Package longtable Warning: Table widths have changed. Rerun LaTeX."
]


def render_latex(template_name, ctx):
    """Render a TeX source from a template name + context, then runs it through PDF LaTeX
    until it reached a fixpoint (tables tend to need several runs until they find a proper layout).
    Return the PDF content as a binary string.
    """    
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


def table(dd):
    template = "subgroup-table.tex" if isinstance(dd, FlatDeliveryDescription) else "delivery-table.tex"
    orientation = "landscape" if len(dd.products) > 18 else "portrait"
    return render_latex(template, {'dd': dd, 'orientation': orientation})


def cards(dd):
    max_order_size = max(len([pc for pc in row.purchases if pc]) for row in dd.rows)
    template = "subgroup-cards.tex" if isinstance(dd, FlatDeliveryDescription) else "delivery-cards.tex"
    return render_latex(template, {'dd': dd, 'max_order_size': max_order_size})


def emails(nw):
    return render_latex("emails.tex", {"nw": nw})
