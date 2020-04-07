Déployer les circuits courts Caracole
=====================================

L'installation se fait de préférence à l'aide de docker et
docker-compose sur une machine Linux. La procédure n'a pas encore été
complètement automatisée, ce document décrit son état actuel.

1. personnaliser l'environnement: editer le fichier `.env`, choisir le
   port sur lequel le site est exporté, le nom, l'e-mail et le mot de
   passe du super-utilisateur (il est administrateur de réseaux et de
   la base de données), les réglages du compte SMTP d'envoi de mail,
   la clef secrete `DJANGO_SECRET_KEY` (celle par défaut se promène
   partout notamment sur Github).
   
   
2. éventuellement faire des réglages avancés dans
   `caracole/settings.py`.
   
3. initialiser la base de fichiers statiques et la base de données:
   `docker-compose up init`

4. lancer le site, soit en mode développement `docker-compose up dev`,
   soit en mode production `docker-compose up --detach prod`
   (le mode dev utilise le service django `manage.py runserver`, qui
   recharge automatiquement le site à chaque modification de fichier,
   mais n'offre ni la tenue en charge ni la sécurité d'un déploiement
   basé sur nginx et wsgi).

5. se logger sur le site avec l'e-mail et le mot de passe
   super-utilisateur, y créer un réseau.

6. modifier le branding du site à votre image: les templates à
   modifier sont dans `floreal/templates` et
   `floreal/static/layout`. Une modification superficielle de
   `layout*.html` et des fichiers CSS dans `layout` suffiront
   probablement, au moins dans un premier temps.

7. une fois que tout fonctionne, passer `DEBUG = False` dans
   `caracole/seetings.py`.
