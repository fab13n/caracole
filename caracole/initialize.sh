#!/bin/bash
TIME=15
echo "Waiting $TIME seconds to make sure the DB is initialized"
sleep $TIME
./manage.py migrate
./manage.py shell <<EOF
from django.contrib.auth.models import User
username = "$SUPERUSER_USERNAME"
kwargs = {
   'username': "$SUPERUSER_EMAIL",
   'first_name': "Caracole",
   'last_name': "Superuser",
   'email': "$SUPERUSER_EMAIL",
   'password': "$SUPERUSER_PASSWORD"
}

try:
    # Retrieve Superuser
    user = User.objects.get(username=username)
    print(f"Superuser {user.id} already exists.")
except User.DoesNotExist:
    # Create + retrieve Superuser
    user = User.objects.create_superuser(**kwargs)
    print(f"Superuser {username} created.")
EOF
