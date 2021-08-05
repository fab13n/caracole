Villes de France
================

English summary: this Django app imports a database of French municipalities into Django.
Since it mostly interest French developers, the rest of this document is in French.

Cette application Django importe la base de données des communes de France proposée par 
[sql.sh](https://sql.sh/736-base-donnees-villes-francaises), dans sa version du 2014-07-02.
Merci de se référer à cette page pour la signification de chaque champ de modele.

Elle permet également d'exploiter les _Plus Codes_, l'utilisation que fait Google du géocodage
[Open Location Code](https://fr.wikipedia.org/wiki/Open_Location_Code) : alors que ces codes
font normalement 11 caractères, Google ne donne typiquement que les 7 derniers, accompagnés
d'un nom de commune proche pour reconstituer les premiers. Par exemple, 
`"GFWR+9Q Ramonville-Saint-Agne"` au lieu de `"8FM3GFWR+9Q"`. Les fonctions du module 
`villes.plus_code` utilisent la base de données pour passer du code Google soit à un objet
`openlocationcode.CodeArea`, soit à des coordonnées latitude + longitude.
