# Guide de déploiement Solalim

Ce document explique comment mettre l'application en service depuis un checkout
Git vierge. Il s'adresse autant aux humains qu'aux agents de développement.

## Prérequis

- Docker et Docker Compose installés.
- Un accès réseau sortant (téléchargement des images Docker, pip, apt).
- Pour la production : un nom de domaine pointant vers le serveur.

## 1. Cloner le dépôt

```bash
git clone <url-du-depot> solalim
cd solalim
```

## 2. Configurer l'environnement

```bash
cp deploy/env.example .env
```

Éditer `.env` et adapter au minimum :

| Variable | Description |
|---|---|
| `SUPERUSER_PASSWORD` | Mot de passe du compte admin Django et de PostgreSQL |
| `SUPERUSER_EMAIL` | Email de l'administrateur |
| `DJANGO_SECRET_KEY` | Chaîne aléatoire longue (ex: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`) |
| `SMTP_*` | Configuration du serveur mail sortant |
| `PUBLIC_HOST` | Nom de domaine public (ou `localhost` pour le dev) |
| `PUBLIC_PROTO` | `http` pour le dev, `https` pour la production |

Le fichier `.env` n'est **pas versionné** (il est dans `.gitignore`).

## 3. Construire et lancer

```bash
# Construire l'image Docker
docker-compose build

# Initialiser la base de données, les fichiers statiques et le super-utilisateur
docker-compose run --rm init

# Lancer l'application
docker-compose up -d
```

L'application est accessible sur `http://localhost:80` (ou le port configuré dans
`PUBLIC_HTTP_PORT`).

## Services Docker

| Service | Rôle |
|---|---|
| `db` | PostgreSQL |
| `django_prod` | Application Django (gunicorn) |
| `dev` | Serveur de développement Django (runserver, port 1234) |
| `prod` | Reverse proxy nginx |
| `init` | Initialisation unique (migrations, collectstatic, création du super-utilisateur) |
| `certbot` | Renouvellement automatique des certificats Let's Encrypt |

Pour le développement local, on peut utiliser le service `dev` seul :

```bash
docker-compose up db dev
```

L'application est alors accessible sur `http://localhost:1234` sans nginx.

## 4. Configuration nginx

La config nginx est montée depuis `deploy/http.conf` (HTTP) ou `deploy/https.conf`
(HTTPS), selon la valeur de `PUBLIC_PROTO` dans `.env`.

Pour le développement, `deploy/http.conf` fonctionne tel quel.

## 5. Passage en HTTPS (production)

1. Copier le template :
   ```bash
   cp deploy/https.conf.example deploy/https.conf
   ```

2. Remplacer `VOTRE_DOMAINE` par le vrai nom de domaine dans `deploy/https.conf`.

3. Obtenir les certificats Let's Encrypt. Il faut d'abord démarrer nginx en HTTP
   pour que certbot puisse répondre au challenge :
   ```bash
   # Temporairement, garder PUBLIC_PROTO=http et lancer nginx
   docker-compose up -d prod

   # Obtenir le certificat
   docker-compose run --rm certbot certonly --webroot \
     -w /var/www/certbot -d votre-domaine.example.com

   # Passer en HTTPS
   # Dans .env, mettre PUBLIC_PROTO=https
   docker-compose up -d prod
   ```

4. Le service `certbot` du docker-compose renouvelle automatiquement les
   certificats.

## 6. Après un `git pull`

```bash
docker-compose build
docker-compose run --rm init    # applique les migrations et collectstatic
docker-compose up -d
```

## Structure du projet

```
solalim/              # Configuration Django (settings, wsgi, urls)
floreal/              # Application principale (modèles, vues, templates)
pages/                # Pages CMS Wagtail
villes/               # Géolocalisation des communes
search/               # Recherche Wagtail
customize_wagtail/    # Personnalisation de l'admin Wagtail
deploy/               # Templates de configuration (non spécifiques à un déploiement)
volumes/              # Données persistantes locales (gitignored)
```

## Variables d'environnement notables

Le fichier `solalim/settings.py` lit toute sa configuration depuis les variables
d'environnement définies dans `.env`. Pas besoin de fichier settings séparé.

Les variables les plus importantes au-delà de celles du `.env` :

- `DEBUG` : `true` pour le dev, `false` en production.
- `ENV` : optionnel, utilisé par le docker-compose de production pour distinguer
  `prod` et `staging`.

## Dépannage

- **La base de données n'est pas prête** : le service `init` attend 15 secondes
  que PostgreSQL démarre. Si ça ne suffit pas, relancer `docker-compose run --rm init`.
- **Les fichiers statiques ne s'affichent pas** : vérifier que `docker-compose run --rm init`
  a bien exécuté `collectstatic`.
- **Erreurs GDAL** : l'image Docker installe GDAL automatiquement. Ne pas essayer
  d'installer les dépendances Python hors Docker.
