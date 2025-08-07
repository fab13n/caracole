from django.db import models

from wagtail.models import Page
from wagtail import fields
from wagtail.admin import panels

class TexteDAccueil(Page):
    texte_accueil = fields.RichTextField()
    parent_page_types = []  # Don't let users create other home pages
    content_panels = Page.content_panels + [
        panels.FieldPanel('texte_accueil', classname="full"),
    ]

class CustomPage(Page):   
    body = fields.RichTextField()
    content_panels = Page.content_panels + [
        panels.FieldPanel('body', classname="full"),
    ]