from django.db import models

from wagtail.core.models import Page
from wagtail.core import fields
from wagtail.admin import edit_handlers

class HomePage(Page):
    texte_accueil = fields.RichTextField()
    parent_page_types = []  # Don't let users create other home pages
    content_panels = Page.content_panels + [
        edit_handlers.FieldPanel('texte_accueil', classname="full"),
    ]

class GareCentrale(Page):   
    body = fields.RichTextField()
    content_panels = Page.content_panels + [
        edit_handlers.FieldPanel('body', classname="full"),
    ]