#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p secrets
chmod 700 secrets
for name in db_admin_password db_app_password patient_one_token patient_two_token staff_token; do
    if [ ! -f "secrets/$name" ]; then
        openssl rand -hex 32 > "secrets/$name"
    fi
done
if [ ! -f .env ]; then cp .env.example .env; fi
chmod 600 secrets/db_admin_password
chmod 644 secrets/db_app_password
for name in patient_one_token patient_two_token staff_token; do
    chgrp "$(id -g)" "secrets/$name"
    chmod 640 "secrets/$name"
done
if grep -q '^HOST_GID=' .env; then
    sed -i "s/^HOST_GID=.*/HOST_GID=$(id -g)/" .env
else
    printf 'HOST_GID=%s\n' "$(id -g)" >> .env
fi
printf '%s\n' 'Created missing local secrets and .env. Existing values were preserved.'
