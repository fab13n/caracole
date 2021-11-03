CAVEAT: ce document décrit la version originale d'un outil de commandes 
en ligne, initialement développé pour l'association Caracole. Cette
version a profondément été revue, suite aux marchés confinés Covid
de 2020 qui ont fait exploser le nombre d'utilisateurs, puis sur
demande du FR CIVAM 31, pour permettre à un public plus nombreux
et moins expérimenté de lancer ses propres circuits. L'ébauche
de document de design ci-dessous n'est plus à jour de cette version
modifiée en profondeur.

Original README
===============

Ce site web permet de gérer la commande et la commande de produits en
vrac. Il a été développé pour l'association Caracole, qui cherche à
favoriser la création et l'extension de circuits courts de produits
alimentaires bio. Il est capable de gérer des réseaux de quelques
centaines de consommateurs.

Principes
=========

Un collectif de producteurs et de consommateurs gère un _réseau_
(_network_), qui propose des _commandes_ (_deliveries_). Chaque
commande propose un ensemble de _produits_ (_products_), dotés d'un
nom, un prix, une unité de mesure (kilogramme, bouteille, pièce...),
éventuellement d'un conditionnement (par exemple 10kg/carton, 6
bouteilles/carton...), qu'un quota (quantité totale disponible).

Lorsqu'une commande est proposée à la vente sur un réseau, les
_membres_ (_users_) inscrits à ce réseau peuvent commander les
produits correspondants. Certains membres sont également _référants_ 
(_admins_), en charge du bon déroulement de la commande. Ils ont accès
à l'état de la commande : qui a commandé quoi, avec tous les totaux en
quantités, en prix, en poids. Ces informations sont accessibles sur
une page web, dans un tableau Excel, et sous forme imprimable (PDF); 
à chaque fois qu'un membre modifie sa commande, tous les tableaux sont
automatiquement mis à jour. Bien sûr, le producteur peu geler la 
commande pour arrêter les modifications avant commande.

TODO: clarifier user, subroup_admin, network_admin, staff, superuser.
Faire la distinction django/floreal.

Passé un certain nombre de membres, il n'est plus pratique de les gérer
de façon monolythique; les membres d'un réseau sont donc répartis en
_sous-groupes_ (_subgroups_), qui correspondent généralement aux
différents lieux de commande d'une commande.

Les sous-groupes ont des référants de sous-groupes (_subgroup admins_),
qui peuvent :

* voir les achats de leur sous-groupe ;

* passer ou modifier des achats au nom de leurs membres ;

* accepter ou refuser les candidatures de membres à leur sous-groupe.

Ils sont responsables de la commande pour leur sous-groupe :
ils s'assurent que chacun à bien payé et reçu ce qu'il
doit, éventuellement ils font des ajustements, notamment en gérant le rab
commandé pour faire des caisses entières. Après la commande, ils doivent
mettre à jour les achats sur le site, pour que la comptabilité tombe juste.

Le site tient le compte des sommes dues, mais ne gère pas directement
d'argent : ça serait compliqué, ça demanderait un niveau de sécurité
considérable, et ça rajouterait un intermédiaire qui nous ferait
sortir de la définition d'un circuit court.

Création d'un réseau
====================

Pour l'instant, ça doit être fait directement en DB ou par l'API
admin Django. Il faut créer un _Network_, au moins un _subgroup_,
mettre un membre comme _user_ et _staff_ des deux. Ensuite, les
membres réguliers s'inscrivent s'ils ne le sont pas déjà, et
l'administrateur du réseeau les ajoute au(x) sous-groupe(s), désigned
éventuellement des administrateurs supplémentaires, avec le lien
"Répartir les membres en sous-groupes".

L'ajout de nouveaux sous-groupes doit aussi se faire directement en
DB.

Cycle de vie d'une commande
============================

1. un admin réseau clique sur "Créer une commande"
2. il liste les produits qu'il veut proposer, éventuellement avec une
   limite de quantités, puis clique sur "Sauvegarder".
3. il clique sur "autoriser les commandes".
4. il prévient les utilisateurs par e-mail (il peut récupérer la liste
   à jour sur le site, lien "e-mails du réseau").
5. après le temps imparti, il ferme la commande aux utilisateurs,
   demande aux admins de sous-groupe de vérifier / compléter la
   commande (par exemple s'assurer qu'elle est faite par caisses
   entières).
6. quand tous les groupes sont régularisés, il prépare la commande,
   d'après la source qu'il préfère (page web, tableau Excel, fiches
   PDF).
7. après commande, il demande aux responsables de sous-groupe de
   s'assurer qu'ils ont bien finalisé la commande, c'est-à-dire qu'ils
   ont reporté sur le site tous les éventuels changements de dernière
   minute.

TODO:
* creer et supprimer des sous-groupes
* creation de comptes: soit permettre de se pre-enregistrer, soit lister les orphelins aux admins sous-groupe.
  On pourrait laisserles gens qui s'inscrivent renseigner leur sous-groupes et les marquer inactifs, puis laisser
  les admins decider soit de les activer, soit de les degager (inactifs + dans aucun groupe). Ca demande de verifier
  l'usage de is_active partout.