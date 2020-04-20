Déployer les circuits courts Caracole
=====================================


Avec Docker
-----------

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
   
3. lancer le script d'initialisation. Il initialisera la base de
   donnée, la base de fichiers statiques, créera les fichiers de
   configuration nginx, et optionellement demandera un certificat
   TLS à letsencrypt `./initialize.sh`.

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


HTTPS
-----

Pour servir le site avec un chiffrement et une authentification
sécurisées (en https plutôt qu'en http donc), il faut posséder un nom
de domaine, servir sur les ports standard 80 et 443, et obtenir un
certificat TLS de la part de Letsencrypt. Des services
`docker-compose` sont inclus dans la distribution pour vous y
aider. Voici les étapes à suivre, dans l'hypothèse où vous n'avez pas
déjà de certificats TLS :

* dans `.env`, régler `PUBLIC_HTTP_PORT=80, PUBLIC_HTTPS_PORT=443` et
  renseigner dans `PUBLIC_HOST` le nom de domaine de votre serveur.

* Lancer le service docker qui demandera à letsencrypt votre premier
  certificat et lui prouvera que le nom de domaine vous appartient :
  `docker-compose up certbot`.


Sans Docker
-----------

1. Mettre à jour les variables d'environnement dans `.env` (cf. Docker
  ci-dessus) 
2. Convertir le fichier de la syntaxe docker-compose en syntaxe bash
3. Evaluer le fichier de variables bash
4. Créer un environnement virtuel Python 3
5. Rentrer dans cet environnement
6. Installer les dépendance PIP dans cet environnement

```
edit .env                              # Configure setup
caracole/env2bash .env > .env.sh       # Convert to bash
. .env.sh                              # Set variables
python3 -m virtualenv venv             # Create virtualenv
. venv/bin/activate                    # Enter virtualenv
pip install -r requirements-python.txt # Install dependencies
```

`psycopg2` peut s'avérer un peu pénible à installer (il a des
dépendances Postgres qui doivent être installées hors virtualenv), et
peu utile : lorsqu'il tourne hors Docker, le site est prévu pour
utiliser préférentiellement un base sqlite3. Vous pouvez le désactiver
en le retirant de `requirements-python.txt`.

Maintenant on peut initialiser la DB:

```
./manage.py migrate         # Initialize DB
./manage.py createsuperuser # Create a superuser. use an email as username
```

À partir de là, vous pouvez faire tourner le serveur de développement :

```
./manage.py runserver 0.0.0.0:8000
```

Pour effectivement déployer, il faudra installer un reverse proxy
(nginx ou apache2 par exemple), l'interfacer en WSGI avec Django grâce
à `uwsgi` ou `Gunicorn`, si possible configurer TLS avec
Letsencrypt. Mais sauf besoins spécifiques, le déploiement avec
`docker-compose` devrait rester le plus simple.
