#!/bin/bash
cd $(dirname $0)/..

# Load configuration
. setenv

# Check basic requirements
if [[ "$PUBLIC_HTTP_PORT" != "80" ]]; then
    echo PUBLIC_HTTP_PORT must be 80 in .env
    exit 1
fi
if [[ "$PUBLIC_HTTPS_PORT" != "443" ]]; then
    echo PUBLIC_HTTPS_PORT must be 443 in .env
    exit 1
fi
if [[ "$PUBLIC_PROTO" != "https" ]]; then
    echo PUBLIC_PROTO must be https in .env
    exit 1
fi

envsubst \
    '$PUBLIC_HOST PUBLIC_HTTP_PORT PUBLIC_HTTPS_PORT' \
    < nginx/certbot.conf.template \
    > $VOLUMES/certbot/default.conf

RSA_KEY_SIZE=4096

echo "### Creating dummy certificate for $PUBLIC_HOST ..."
DOCKER_PATH="/etc/letsencrypt/live/$PUBLIC_HOST"
HOST_PATH=$VOLUMES/certbot/conf/live/$PUBLIC_HOST
if [[ -f  $HOST_PATH/privkey.pem && -f $HOST_PATH/fullchain.pem ]]; then
    echo "Possibly dummy certificate and key found"
else
    mkdir -p $HOST_PATH
    docker-compose run --rm --entrypoint "\
        openssl req -x509 -nodes -newkey rsa:1024 -days 1\
        -keyout '$DOCKER_PATH/privkey.pem' \
        -out '$DOCKER_PATH/fullchain.pem' \
        -subj '/CN=localhost'" certbot
fi

echo "### Starting nginx to serve challenge..."
docker-compose up --force-recreate --detach certbot_nginx
echo

echo "### Deleting dummy certificate for $PUBLIC_HOST ..."
rm -Rf $VOLUMES/certbot/conf/{live,archive,renewal}/$PUBLIC_HOST
echo

echo "### Requesting Let's Encrypt certificate for $PUBLIC_HOST ..."
docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $SUPERUSER_EMAIL \
    -d $PUBLIC_HOST \
    --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos \
    --force-renewal" certbot
echo

echo "### Switch off certbot challenge nginx ..."
docker-compose stop -t 1 certbot_nginx

