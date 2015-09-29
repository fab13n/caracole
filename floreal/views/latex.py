import os
from tempfile import NamedTemporaryFile

from django import template
from django.template.loader import get_template

from floreal.views.delivery_description import delivery_description


def _run(descr, template_name):
    t = get_template(template_name)
    tex_unicode = t.render(template.Context({'d': descr}))
    tex_string = tex_unicode.encode('utf8')
    with NamedTemporaryFile(suffix='.tex', delete=False) as f:
        f.write(tex_string)
        f.flush()
        src_file_name = f.name
        dst_file_name = os.path.splitext(src_file_name)[0]+".pdf"
        print "Generated tex file %s" % src_file_name
        os.chdir("/tmp/")
        # TODO: popen + grep to get the warning about tables to be re-run
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        os.system("pdflatex -halt-on-error %s" % src_file_name)
        with open(dst_file_name, "r") as g:
            pdf_string = g.read()
    return pdf_string

def cards(dv, sg):
    descr = delivery_description(dv, [sg])
    return _run(descr, "cards.tex")

def subgroup(dv, sg):
    descr = delivery_description(dv, [sg])
    return _run(descr, "subgroup.tex")

def delivery(dv):
    descr = delivery_description(dv, dv.network.subgroup_set.all())
    return _run(descr, "delivery.tex")
