#!/usr/bin/python3
# -*- coding: utf-8 -*-

from django import forms
from .models import Delivery, Product
from django.forms import formset_factory

class ProductForm(forms.ModelForm):
    """Sous forme d'une table, on a besoin d'initier les donnees, il faut recuperer l'id
    d'un produit et rajouter les flêches pour le swap
    on affiche un produit sur une ligne dans un <table> 
    On a une foreign key vers Delivery dans le modèle
    Rappel : manytomany fields are processed by a ModelMultipleChoiceField
    ForeignKey par un ChoiceField, ce qu'on ne veut pas"""
    #def __init__(self,*args, **kwargs) :
    #    super().__init__(self,*args,**kwargs) 
    #    self.auto_id=False
        
    ajoute_desc = forms.BooleanField() # Faut-il rajouter une description au produit ou effacer le champ description
    effacer = forms.BooleanField() # Faut-il effacer le produit après la requête   
    def __str__(self):
        return self.as_div_in_td

    def as_div_in_td(self):
    # pour être appelé dans le formulaire 
        return self._html_output(
            normal_row='<td%(html_class_attr)s><div>%(errors)s%(field)s%(help_text)s</div></td>',
            error_row='', # pas d'error pour un élément du tableau
            row_ender='</div></td>',
            help_text_html='<br><span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )  
    class Meta:
        model = Product # recupère tous les champs
        exclude = ('delivery',)

ProductFormset = formset_factory(ProductForm, extra =1) 



class DeliveryForm(forms.ModelForm):
    """Le formulaire pour editer une livraison, template edit_delivery_products
    Utilisation possible de ce qui s'appelle dans la doc formulaires groupés
    C'est l'ensembe deux formulaires : un de Delivery et un ensemble de ProductForm
    On intialise un objet de type Form avec request.POST et on passe comme argument
    au template 'form' : form avec form de type Form 
   """
      

    class Meta:
        model = Delivery
        exclude = ('datedelivery','network')
        # l'autre syntaxe est fields pour spécifier les fields


