#!/bin/bash
cd $(dirname $0)
. setenv

mkdir -p $VOLUMES

if [[ "$POSTGRES_DBNAME" == "" ]]; then
    touch $VOLUMES/database.sqlite3
fi

envsubst \
    '$PUBLIC_HOST $PUBLIC_HTTP_PORT $PUBLIC_HTTPS_PORT' \
    < nginx/$PUBLIC_PROTO.conf.template \
    > $VOLUMES/$PUBLIC_PROTO.conf

echo "## Create and fill the database"
docker-compose up --build init
# TODO make it idempotent

if [[ "$PUBLIC_PROTO" == "https" ]]; then
    nginx/get_certificate.sh || exit 1
fi

