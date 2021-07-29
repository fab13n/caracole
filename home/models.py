from django.db import models

from wagtail.core.models import Page
from wagtail.core import fields
from wagtail.admin import edit_handlers

class HomePage(Page):
    pass


class GareCentrale(Page):   
    body = fields.RichTextField()
    content_panels = Page.content_panels + [
        edit_handlers.FieldPanel('body', classname="full"),
    ]