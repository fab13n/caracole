""" Define preview URL. """

from django.urls import path

from django_markdown.views import preview

urlpatterns = [
    path('preview/', preview, name='django_markdown_preview')
]
